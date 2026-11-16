import { useState } from 'react'
import logo from './assets/brand/jbyouthhub-logo.png'
import OfficerConsole from './pages/officer/OfficerConsole.tsx'
import './app-shell.css'

export default function App() {
  const [homeKey, setHomeKey] = useState(0)
  return (
    <div className="app-shell">
      <header className="shell">
        <div className="shell__inner">
          <button className="shell__home" type="button" aria-label="신청 목록으로 이동" onClick={() => {
            const mock = new URLSearchParams(window.location.search).get('mock') === '1'
            window.history.pushState(null, '', mock ? '/officer?mock=1' : '/officer')
            setHomeKey((value) => value + 1)
          }}><img className="shell__logo" src={logo} alt="전북청년허브센터" /></button>
          <span className="shell__role">담당자</span>
        </div>
      </header>
      <OfficerConsole key={homeKey} />
    </div>
  )
}
