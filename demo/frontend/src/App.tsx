import { useState } from 'react'
import logo from './assets/brand/jb-logo.png'
import OfficerConsole from './pages/officer/OfficerConsole.tsx'
import OfficerSession from './pages/officer/OfficerSession.tsx'
import './app-shell.css'

export default function App() {
  const [homeKey, setHomeKey] = useState(0)
  // 로그인 상태 줄(로그아웃 버튼)을 머리글 오른쪽에 그릴 자리.
  const [sessionHost, setSessionHost] = useState<HTMLDivElement | null>(null)
  return (
    <div className="app-shell">
      <header className="shell">
        <div className="shell__inner">
          <button className="shell__home" type="button" aria-label="처음으로" onClick={() => {
            const mock = new URLSearchParams(window.location.search).get('mock') === '1'
            window.history.pushState(null, '', mock ? '/officer?mock=1' : '/officer')
            setHomeKey((value) => value + 1)
          }}><img className="shell__logo" src={logo} width={275} height={67} alt="전북특별자치도 2026 전북청년 함께 두배적금" /></button>
          <span className="shell__role">담당자</span>
          <div className="shell__session" ref={setSessionHost} />
        </div>
      </header>
      <OfficerSession headerHost={sessionHost}>
        <OfficerConsole key={homeKey} />
      </OfficerSession>
    </div>
  )
}
