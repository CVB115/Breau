// src/components/BottomNav.tsx
import { Link, useLocation } from "react-router-dom";
import { Home, Coffee, User } from "lucide-react"; // replace with your icon lib if needed

export default function BottomNav() {
  const { pathname } = useLocation();
  const is = (p: string) => pathname === p || pathname.startsWith(p + "/");

  return (
    <nav className="bottom-nav">
      <Link to="/" className={`nav-btn ${is("/") ? "active" : ""}`}>
        <Home size={20} /><div>Home</div>
      </Link>
      <Link to="/brew" className={`nav-btn ${is("/brew") ? "active" : ""}`}>
        <Coffee size={20} /><div>Brew</div>
      </Link>
      <Link to="/profile" className={`nav-btn ${is("/profile") ? "active" : ""}`}>
        <User size={20} /><div>Profile</div>
      </Link>
    </nav>
  );
}
