import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { ThemeToggle } from '../components/ThemeToggle';

// App layout: persistent sidebar + a slim topbar, with the active route
// rendered into <Outlet/>. Page content (header, body) lives in each page.
export function Shell() {
  return (
    <div className="app">
      <Sidebar />
      <div className="app-main">
        <header className="topbar">
          <ThemeToggle />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
