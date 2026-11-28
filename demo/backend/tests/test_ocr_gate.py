"""11-28: 문서 판독은 이벤트 루프 밖 작업 스레드에서, 프로세스당 한 건씩, 대기 상한 안에서 돈다 (가상 문서만).

수정 전: 업로드 처리(async)가 판독을 이벤트 루프에서 직접 돌려, 한 건을 읽는 동안 그 프로세스의 모든 요청이 멈췄다.
여기서는 가짜 판독기(실제 OCR 없음)로 실행 모델만 확인한다: 루프 응답성, 동시 실행 1건, 대기 상한 503, 취소,
신청자 간 결과 분리, 파일 교체, 판독 중 신청 변경(409), 저장소·DB 정리.
"""
import asyncio
import contextvars
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pymupdf
import pytest
from sqlmodel import select

from demo.backend import application_writes, models, ocr_gate
from demo.backend.api import common, documents
from demo.backend.ocr.base import OcrResult
from demo.backend.rules.doc_types import DocType
from demo.backend.tests.test_portal_uploads import client, new_app  # noqa: F401 - fixture

SLOT = "resident_abstract"


@pytest.fixture(autouse=True)
def fresh_gate():
    """시험마다 기다리던 판독을 비우고 시작하고, 끝나면 자리가 모두 비었는지 확인한다(누수 금지)."""
    ocr_gate.shutdown()
    yield
    deadline = time.monotonic() + 5
    while ocr_gate.admitted() and time.monotonic() < deadline:
        time.sleep(.01)
    assert ocr_gate.admitted() == 0
    ocr_gate.shutdown()


# ================================================================ 게이트 단위


def test_reads_run_one_at_a_time_in_a_worker_thread_and_the_loop_keeps_running():
    state = {"now": 0, "max": 0, "threads": set()}
    lock = threading.Lock()

    def read(index):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
            state["threads"].add(threading.current_thread().name)
        time.sleep(.4)  # 이벤트 루프에서 돌았다면 이 동안 루프가 멈춘다
        with lock:
            state["now"] -= 1
        return index

    async def one(index):
        with ocr_gate.reserve() as ticket:
            return await ticket.run(read, index)

    async def exercise():
        loop_thread = threading.current_thread().name
        gaps, last, stop = [], time.monotonic(), False

        async def ticker():
            nonlocal last
            while not stop:
                await asyncio.sleep(.01)
                now = time.monotonic(); gaps.append(now - last); last = now
        tick = asyncio.create_task(ticker())
        results = await asyncio.gather(*(one(i) for i in range(4)))
        stop = True
        await tick
        return loop_thread, results, max(gaps)

    loop_thread, results, longest_gap = asyncio.run(exercise())
    assert results == [0, 1, 2, 3]
    assert state["max"] == ocr_gate.MAX_CONCURRENT_READS == 1          # 문서는 한 건씩만 읽는다
    assert loop_thread not in state["threads"] and all(name.startswith("ocr-read") for name in state["threads"])
    assert longest_gap < .3                                             # 판독 1.6초 동안 루프는 멈추지 않았다(루프에서 돌면 0.4초 이상)


def test_full_queue_is_refused_and_recovers(monkeypatch):
    monkeypatch.setattr(ocr_gate, "MAX_WAITING_READS", 1)
    entered, release = threading.Event(), threading.Event()

    def blocking():
        entered.set()
        assert release.wait(5)
        return "read"

    async def exercise():
        async def one(function):
            with ocr_gate.reserve() as ticket:
                return await ticket.run(function)
        first = asyncio.create_task(one(blocking))
        await asyncio.to_thread(entered.wait, 5)
        second = asyncio.create_task(one(lambda: "waited"))        # 대기 1건: 허용
        await asyncio.sleep(.05)
        assert ocr_gate.admitted() == 2
        with pytest.raises(ocr_gate.OcrBusy) as refused:           # 대기열 가득: 거절
            with ocr_gate.reserve():
                raise AssertionError("must not be admitted")
        assert refused.value.status_code == 503 and refused.value.headers["Retry-After"]
        assert ocr_gate.admitted() == 2                            # 거절은 자리를 쓰지 않는다
        release.set()
        assert await first == "read" and await second == "waited"
        with ocr_gate.reserve() as ticket:                         # 회복: 다시 받는다
            assert await ticket.run(lambda: "again") == "again"
    asyncio.run(exercise())


def test_cancelled_waiting_read_never_starts(monkeypatch):
    entered, release, started = threading.Event(), threading.Event(), []

    async def exercise():
        async def one(function):
            with ocr_gate.reserve() as ticket:
                return await ticket.run(function)
        first = asyncio.create_task(one(lambda: (entered.set(), release.wait(5))[1]))
        await asyncio.to_thread(entered.wait, 5)
        waiting = asyncio.create_task(one(lambda: started.append("ran")))
        await asyncio.sleep(.05)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert ocr_gate.admitted() == 1                            # 취소된 대기 건은 자리를 바로 놓는다
        release.set()
        assert await first is True
    asyncio.run(exercise())
    time.sleep(.1)
    assert started == []                                           # 시작 전 취소: 실행되지 않았다


def test_cancelled_running_read_keeps_its_place_until_it_really_ends():
    """실행 중인 판독은 멈출 수 없다. 끝날 때까지 자리를 차지하고(다음 판독은 그 뒤), 파일 정리도 끝난 뒤에 한다."""
    entered, release, order = threading.Event(), threading.Event(), []

    def long_read():
        entered.set()
        assert release.wait(5)
        order.append("first-read-ended")

    async def exercise():
        async def abandoned():
            with ocr_gate.reserve() as ticket:
                try:
                    await ticket.run(long_read)
                finally:
                    ticket.after_read(lambda: order.append("cleanup"))
        task = asyncio.create_task(abandoned())
        await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert order == [] and ocr_gate.admitted() == 1            # 요청은 끝났지만 판독은 아직 돈다
        with ocr_gate.reserve() as ticket:
            following = asyncio.ensure_future(ticket.run(lambda: order.append("next-read")))
            await asyncio.sleep(.1)
            assert order == []                                     # 다음 판독은 겹쳐 돌지 않는다
            release.set()
            await following
    asyncio.run(exercise())
    assert order == ["first-read-ended", "cleanup", "next-read"]


def test_queue_wait_deadline_returns_busy_without_starting(monkeypatch):
    entered, release, started = threading.Event(), threading.Event(), []

    async def exercise():
        async def one(function):
            with ocr_gate.reserve() as ticket:
                return await ticket.run(function)
        first = asyncio.create_task(one(lambda: (entered.set(), release.wait(5))[1]))
        await asyncio.to_thread(entered.wait, 5)
        monkeypatch.setattr(ocr_gate, "MAX_QUEUE_WAIT_SECONDS", .1)   # 첫 판독이 시작된 뒤에 시한을 줄인다
        with pytest.raises(ocr_gate.OcrBusy):
            await one(lambda: started.append("ran"))               # 차례가 시한 안에 오지 않았다
        assert ocr_gate.admitted() == 1
        release.set()
        assert await first is True                                 # 시한은 실행 중인 판독을 끊지 않는다
    asyncio.run(exercise())
    time.sleep(.1)
    assert started == []


def test_reader_sees_the_request_context_and_errors_reach_the_caller():
    marker = contextvars.ContextVar("marker", default="unset")

    async def exercise():
        marker.set("request-context")
        with ocr_gate.reserve() as ticket:
            assert await ticket.run(marker.get) == "request-context"
        with ocr_gate.reserve() as ticket:
            with pytest.raises(ZeroDivisionError):
                await ticket.run(lambda: 1 / 0)
        with ocr_gate.reserve() as ticket:
            await ticket.run(lambda: None)
            with pytest.raises(RuntimeError):
                await ticket.run(lambda: None)                     # 자리 하나에 판독 한 번
    asyncio.run(exercise())


def test_shutdown_drops_waiting_reads_and_never_overlaps_the_running_read():
    entered, release, started = threading.Event(), threading.Event(), []

    async def exercise():
        async def one(function):
            with ocr_gate.reserve() as ticket:
                return await ticket.run(function)
        first = asyncio.create_task(one(lambda: (entered.set(), release.wait(5))[1]))
        await asyncio.to_thread(entered.wait, 5)
        waiting = asyncio.create_task(one(lambda: started.append("ran")))
        await asyncio.sleep(.05)
        ocr_gate.shutdown()                                        # 기다리던 판독은 버리고, 도는 판독은 기다리지 않는다
        with pytest.raises(ocr_gate.OcrBusy):                      # 요청이 취소된 것이 아니다: 503으로 알린다
            await waiting
        threads = []
        after = asyncio.create_task(one(lambda: threads.append(threading.current_thread().name) or "after-shutdown"))
        await asyncio.sleep(.1)
        assert threads == []                                       # 종료 뒤에도 앞 판독이 끝나야 다음을 읽는다(동시 1건)
        release.set()
        assert await first is True
        assert await after == "after-shutdown"
    asyncio.run(exercise())
    assert started == []


# ================================================================ 업로드 API


def _pdf(text):
    with pymupdf.open() as document:
        document.new_page().insert_text((40, 50), text, fontname="korea")
        return document.tobytes()


def _post(client, aid, content, name="FAKE-upload.pdf"):
    return client.post(f"/api/applications/{aid}/documents", data={"slot_key": SLOT},
                       files={"file": (name, content, "application/pdf")})


def _rows(aid):
    with models.get_session() as session:
        return session.exec(select(models.Document).where(models.Document.application_id == aid)).all()


def _stored_files(aid):
    with models.get_session() as session:
        number = session.get(models.Application, aid).application_no
    folder = common.STORAGE / "documents" / number
    return [path for path in folder.rglob("*") if path.is_file()] if folder.exists() else []


class Reader:
    """가짜 판독기. 파일 내용의 해시를 결과에 담아 '누구의 파일을 읽은 결과인지' 추적하고, 원하면 멈춰 세운다."""

    def __init__(self, hold=False):
        self.entered, self.release = threading.Event(), threading.Event()
        self.hold = hold
        self.lock = threading.Lock()
        self.now = self.max = 0
        self.threads, self.contexts, self.calls = [], [], []

    def __call__(self, file_path, expected=None):
        with self.lock:
            self.now += 1
            self.max = max(self.max, self.now)
            self.threads.append(threading.current_thread().name)
            self.contexts.append(models._session_bind.get() is None)
        digest = hashlib.sha256(open(file_path, "rb").read()).hexdigest()
        self.calls.append(digest)
        self.entered.set()
        try:
            if self.hold:
                assert self.release.wait(5)
            else:
                time.sleep(.05)
        finally:
            with self.lock:
                self.now -= 1
        return OcrResult(detected_doc_type=DocType.RESIDENT_ABSTRACT, confidence=.95, image_quality=.9,
                         fields={"합성파일해시": digest}, page_count=1, tier="localocr", engine="synthetic")


def test_other_requests_are_answered_while_a_document_is_being_read(client, monkeypatch):
    """수정 전에는 판독이 끝날 때까지 /api/health도 응답하지 않았다."""
    reader = Reader(hold=True)
    monkeypatch.setattr(documents, "read_document", reader)
    aid = new_app(client)
    with ThreadPoolExecutor(1) as pool:
        upload = pool.submit(_post, client, aid, _pdf("SYNTHETIC ONE"))
        try:
            assert reader.entered.wait(5)
            started = time.monotonic()
            health = client.get("/api/health")
            elapsed = time.monotonic() - started
            still_reading = not reader.release.is_set() and not upload.done()
        finally:
            reader.release.set()
        assert upload.result(timeout=10).status_code == 200
    assert health.status_code == 200 and still_reading and elapsed < 1
    assert all(name.startswith("ocr-read") for name in reader.threads)     # 이벤트 루프가 아닌 판독 스레드
    assert all(reader.contexts)                                             # DB 쓰기 예약 밖에서 읽는다


def test_full_queue_returns_503_before_anything_is_stored(client, monkeypatch):
    monkeypatch.setattr(ocr_gate, "MAX_WAITING_READS", 0)
    reader = Reader(hold=True)
    monkeypatch.setattr(documents, "read_document", reader)
    first, second = new_app(client), new_app(client)
    with ThreadPoolExecutor(1) as pool:
        upload = pool.submit(_post, client, first, _pdf("SYNTHETIC FIRST"))
        try:
            assert reader.entered.wait(5)
            refused = _post(client, second, _pdf("SYNTHETIC SECOND"))
            assert refused.status_code == 503 and refused.headers["retry-after"] == str(ocr_gate.RETRY_AFTER_SECONDS)
            assert refused.json() == {"detail": ocr_gate.BUSY_MESSAGE}
            assert _rows(second) == [] and _stored_files(second) == []     # 거절된 업로드는 흔적이 없다
        finally:
            reader.release.set()
        assert upload.result(timeout=10).status_code == 200
    again = _post(client, second, _pdf("SYNTHETIC SECOND"))                 # 회복: 같은 업로드가 이제 처리된다
    assert again.status_code == 200 and len(_rows(second)) == 1 and len(_stored_files(second)) == 1


def test_upload_that_waited_past_the_deadline_is_sent_back_unread_with_nothing_stored(client, monkeypatch):
    """차례가 시한 안에 오지 않은 업로드: 읽지 않고 503. 이때는 파일을 이미 저장소에 두었으므로 그 파일도 지운다."""
    reader = Reader(hold=True)
    monkeypatch.setattr(documents, "read_document", reader)
    first, second = new_app(client), new_app(client)
    with ThreadPoolExecutor(1) as pool:
        upload = pool.submit(_post, client, first, _pdf("SYNTHETIC FIRST"))
        try:
            assert reader.entered.wait(5)
            monkeypatch.setattr(ocr_gate, "MAX_QUEUE_WAIT_SECONDS", .2)     # 첫 판독이 시작된 뒤에 시한을 줄인다
            late = _post(client, second, _pdf("SYNTHETIC SECOND"))
            assert late.status_code == 503 and late.json() == {"detail": ocr_gate.BUSY_MESSAGE}
            assert _rows(second) == [] and _stored_files(second) == []
            assert len(reader.calls) == 1                                   # 두 번째 파일은 읽지 않았다
        finally:
            reader.release.set()
        assert upload.result(timeout=10).status_code == 200                 # 실행 중이던 판독은 영향받지 않는다
    assert len(_rows(first)) == 1


def test_read_is_never_dispatched_inside_the_database_writer_reservation(client, monkeypatch):
    """판독은 DB 쓰기 예약 밖에서만 맡긴다(예약 연결이 판독 스레드로 넘어가면 안 된다)."""
    aid = new_app(client)
    monkeypatch.setattr(documents, "read_document", Reader())

    async def inside_reservation():
        import io
        from starlette.datastructures import UploadFile
        async with models.async_session_transaction():
            upload = UploadFile(io.BytesIO(_pdf("SYNTHETIC")), filename="FAKE.pdf")
            with pytest.raises(RuntimeError, match="writer reservation"):
                await documents.upload_document(aid, upload, SLOT, None)
    asyncio.run(inside_reservation())
    assert _rows(aid) == [] and _stored_files(aid) == []


def test_command_line_tool_reads_inline_inside_its_own_writer_reservation(client, monkeypatch):
    """합성 시드 같은 단일 스레드 도구는 쓰기 예약 안에서 업로드한다: 판독은 그 스레드에서 바로 돌고 저장된다."""
    aid = new_app(client)
    reader = Reader()
    monkeypatch.setattr(documents, "read_document", reader)
    main_thread = threading.current_thread().name

    with models.session_transaction():
        with ocr_gate.inline_reads():
            import io
            from starlette.datastructures import UploadFile
            upload = UploadFile(io.BytesIO(_pdf("SYNTHETIC TOOL")), filename="FAKE.pdf")
            asyncio.run(documents.upload_document(aid, upload, SLOT, None))
        assert not ocr_gate.reads_inline()                      # 도구 구간을 나오면 꺼진다
    assert len(_rows(aid)) == 1 and len(_stored_files(aid)) == 1
    assert reader.threads == [main_thread]                       # 판독 스레드로 넘기지 않았다
    assert reader.contexts == [False]                            # 도구의 쓰기 예약 안에서 읽었다
    assert ocr_gate.admitted() == 0                              # 자리를 돌려놓았다


def test_inline_read_releases_its_seat_and_runs_cleanup_when_the_read_fails():
    cleaned = []

    def broken():
        raise ValueError("SYNTHETIC")

    async def scenario():
        with ocr_gate.inline_reads(), ocr_gate.reserve() as ticket:
            with pytest.raises(ValueError):
                await ticket.run(broken)
            ticket.after_read(lambda: cleaned.append(threading.current_thread().name))
    asyncio.run(scenario())
    assert cleaned == [threading.current_thread().name] and ocr_gate.admitted() == 0


def test_concurrent_uploads_of_different_applicants_keep_their_own_file_and_result(client, monkeypatch):
    reader = Reader()
    monkeypatch.setattr(documents, "read_document", reader)
    apps = [new_app(client) for _ in range(6)]
    contents = {aid: _pdf(f"SYNTHETIC APPLICANT {index}") for index, aid in enumerate(apps)}
    with ThreadPoolExecutor(len(apps)) as pool:
        responses = list(pool.map(lambda aid: _post(client, aid, contents[aid], f"FAKE-{aid}.pdf"), apps))
    assert [r.status_code for r in responses] == [200] * len(apps)
    assert reader.max == 1                                                  # 문서 판독은 겹치지 않았다
    for aid in apps:
        expected = hashlib.sha256(contents[aid]).hexdigest()
        (row,) = _rows(aid)
        files = _stored_files(aid)
        assert row.ocr_json["fields"]["합성파일해시"] == expected            # 그 신청자의 파일을 읽은 결과
        assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in files] == [expected]   # 원본 그대로, 한 벌
        assert (common.STORAGE.parent / row.file_path) == files[0]


def test_replacing_a_file_never_leaves_the_earlier_verdict(client, monkeypatch):
    """같은 칸에 연달아 올리면 마지막 파일의 판독 결과만 남는다(이전 파일의 적합 잔존 금지). 원본은 둘 다 보존."""
    reader = Reader()
    monkeypatch.setattr(documents, "read_document", reader)
    aid = new_app(client)
    first, second = _pdf("SYNTHETIC OLD"), _pdf("SYNTHETIC NEW")
    assert _post(client, aid, first).status_code == 200
    with ThreadPoolExecutor(2) as pool:                                     # 두 번째·세 번째 교체가 동시에 도착
        results = list(pool.map(lambda content: _post(client, aid, content), [second, first]))
    assert [r.status_code for r in results] == [200, 200]
    (row,) = _rows(aid)                                                     # 칸에는 한 건만
    stored = (common.STORAGE.parent / row.file_path).read_bytes()
    assert row.ocr_json["fields"]["합성파일해시"] == hashlib.sha256(stored).hexdigest()   # 판정과 파일이 같은 업로드
    assert len(_stored_files(aid)) == 3 and reader.max == 1                 # 올린 원본은 덮어쓰지 않는다


def test_application_changed_during_the_read_is_rejected_and_cleaned_up(client, monkeypatch):
    """판독을 기다리는 동안 신청 내용이 바뀌면(다른 프로세스 등) 예전 입력으로 판정한 결과를 저장하지 않는다(409)."""
    reader = Reader(hold=True)
    monkeypatch.setattr(documents, "read_document", reader)
    aid = new_app(client)
    with ThreadPoolExecutor(1) as pool:
        upload = pool.submit(_post, client, aid, _pdf("SYNTHETIC"))
        try:
            assert reader.entered.wait(5)
            with models.get_session() as session:                           # 잠금을 거치지 않는 외부 변경을 흉내 낸다
                application = session.get(models.Application, aid)
                application.identity_json = {"name": "가상변경", "birth": "1999-01-01"}
                session.add(application)
                session.commit()
        finally:
            reader.release.set()
        response = upload.result(timeout=10)
    assert response.status_code == 409
    assert _rows(aid) == [] and _stored_files(aid) == []


def test_reader_failure_leaves_no_row_and_no_file_and_the_next_upload_works(client, monkeypatch):
    aid = new_app(client)
    original = documents.assess_upload

    def broken(*args, **kwargs):
        raise RuntimeError("synthetic assessment failure")
    monkeypatch.setattr(documents, "assess_upload", broken)
    with pytest.raises(RuntimeError):
        _post(client, aid, _pdf("SYNTHETIC"))
    assert _rows(aid) == [] and _stored_files(aid) == []
    monkeypatch.setattr(documents, "assess_upload", original)
    monkeypatch.setattr(documents, "read_document", Reader())
    assert _post(client, aid, _pdf("SYNTHETIC")).status_code == 200
    assert len(_rows(aid)) == 1 and len(_stored_files(aid)) == 1


def test_cancelled_upload_removes_its_file_only_after_the_read_ends(client, monkeypatch, tmp_path):
    """요청이 취소돼도 판독 중인 파일은 판독이 끝난 뒤에 지운다. 행은 저장되지 않고, 잠금은 다음 업로드에 넘어간다."""
    from starlette.datastructures import UploadFile

    reader = Reader(hold=True)
    monkeypatch.setattr(documents, "read_document", reader)
    aid = new_app(client)
    seen = {}

    async def exercise():
        import io
        upload = UploadFile(io.BytesIO(_pdf("SYNTHETIC CANCELLED")), filename="FAKE-cancelled.pdf")
        task = asyncio.create_task(documents.upload_document(aid, upload, SLOT, None))
        await asyncio.to_thread(reader.entered.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        seen["files_while_reading"] = len(_stored_files(aid))
        seen["admitted_while_reading"] = ocr_gate.admitted()
        reader.release.set()
    asyncio.run(exercise())
    deadline = time.monotonic() + 5
    while (ocr_gate.admitted() or _stored_files(aid)) and time.monotonic() < deadline:
        time.sleep(.01)
    assert seen == {"files_while_reading": 1, "admitted_while_reading": 1}   # 읽는 중: 파일 유지, 자리 차지
    assert _stored_files(aid) == [] and _rows(aid) == []                      # 끝난 뒤: 정리됨, 저장 없음
    reader.hold = False
    assert _post(client, aid, _pdf("SYNTHETIC RETRY")).status_code == 200     # 재시도는 정상 처리
    assert len(_rows(aid)) == 1


def test_application_write_lock_is_reentrant_inside_the_reader(client, monkeypatch):
    """판독 스레드는 요청의 문맥을 이어받는다: 요청이 쥔 신청 쓰기 잠금을 판독 안에서 다시 잡아도 멈추지 않는다."""
    aid = new_app(client)
    reader = Reader()

    def reading(file_path, expected=None):
        with application_writes.application_write(aid):
            return reader(file_path, expected)
    monkeypatch.setattr(documents, "read_document", reading)
    with ThreadPoolExecutor(1) as pool:
        assert pool.submit(_post, client, aid, _pdf("SYNTHETIC")).result(timeout=10).status_code == 200
