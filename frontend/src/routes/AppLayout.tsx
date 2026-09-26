import { Link, Outlet, useLocation } from "react-router-dom";

const TABS = [
  { to: "/app", label: "Board", exact: true },
  { to: "/app/create", label: "Create" },
  { to: "/app/portfolio", label: "Portfolio" },
  { to: "/app/activity", label: "Activity" },
  { to: "/app/docs", label: "Docs" },
];

export function AppLayout() {
  const { pathname } = useLocation();
  return (
    <div className="container">
      <div className="app-tabs">
        {TABS.map((t) => {
          const active = t.exact ? pathname === t.to : pathname.startsWith(t.to);
          return (
            <Link key={t.to} to={t.to} className={`app-tab ${active ? "active" : ""}`}>
              {t.label}
            </Link>
          );
        })}
      </div>
      <div style={{ padding: "32px 0 80px" }}>
        <Outlet />
      </div>
    </div>
  );
}
