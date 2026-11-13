import { useState } from 'react'
import OfficerConsole from './pages/officer/OfficerConsole.tsx'
import './app-shell.css'

export default function App() {
  const [homeKey, setHomeKey] = useState(0)
  return (
    <div className="app-shell">
      <header className="shell">
        <button className="shell__mark" type="button" aria-label="서류 목록으로 이동" onClick={() => {
          const mock = new URLSearchParams(window.location.search).get('mock') === '1'
          window.history.pushState(null, '', mock ? '/officer?mock=1' : '/officer')
          setHomeKey((value) => value + 1)
        }}>전북</button>
        <div><strong>전북청년 함께 두배적금</strong><small>담당자 서류 검토</small></div>
      </header>
      <OfficerConsole key={homeKey} />
    </div>
  )
}
