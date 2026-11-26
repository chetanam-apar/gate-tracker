import { useEffect, useState } from "react";
import ChartsPage from "./pages/ChartsPage.jsx";
import GenresPage from "./pages/GenresPage.jsx";
import RunsPage from "./pages/RunsPage.jsx";

// The page list. To add a page: make a file in pages/ and add one line here.
const PAGES = {
  charts: { label: "Charts", component: ChartsPage },
  genres: { label: "Genre trends", component: GenresPage },
  runs: { label: "Run history", component: RunsPage },
};

// The page name lives in the address (http://localhost:5173/#genres),
// so refreshing the browser keeps you on the same page.
function pageFromAddress() {
  const name = window.location.hash.replace("#", "");
  return PAGES[name] ? name : "charts";
}

export default function App() {
  const [page, setPage] = useState(pageFromAddress);

  useEffect(() => {
    const onChange = () => setPage(pageFromAddress());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const Page = PAGES[page].component;

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="brand">🎮 Game Tracker</div>
        {Object.entries(PAGES).map(([key, p]) => (
          <a key={key} href={`#${key}`} className={`nav-item ${page === key ? "active" : ""}`}>
            {p.label}
          </a>
        ))}
      </nav>
      <main className="content">
        <Page />
      </main>
    </div>
  );
}
