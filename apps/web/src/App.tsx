import { Outlet } from "react-router-dom";

export function App() {
  return (
    <div className="app-shell">
      <Outlet />
    </div>
  );
}
