import { useState } from "react";
import ChartsPage from "./pages/ChartsPage.jsx";
import RunsPage from "./pages/RunsPage.jsx";

// The page list. To add a page: make a file in pages/ and add one line here.
const PAGES = {
  charts: { label: "Charts", component: ChartsPage },
  runs: { label: "Run history", component: RunsPage },
};

export default function App() {
  const [page, setPage] = useState("charts");
  const Page = PAGES[page].component;

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="brand">🎮 Game Tracker</div>
        {Object.entries(PAGES).map(([key, p]) => (
          <button key={key} className={`nav-item ${page === key ? "active" : ""}`} onClick={() => setPage(key)}>
            {p.label}
          </button>
        ))}
      </nav>
      <main className="content">
        <Page />
      </main>
    </div>
  );
}
