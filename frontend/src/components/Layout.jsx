import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { clearToken, getToken, logout } from "../modules/auth/service";
import NotificationCenter from "./NotificationCenter";

export default function Layout({ children }) {
  const navigate = useNavigate();
  const token = getToken();
  const [openMenu, setOpenMenu] = useState("");

  async function handleLogout() {
    try {
      await logout();
    } finally {
      clearToken();
      setOpenMenu("");
      navigate("/login");
    }
  }

  function toggleMenu(menuKey) {
    setOpenMenu((prev) => (prev === menuKey ? "" : menuKey));
  }

  function closeMenus() {
    setOpenMenu("");
  }

  return (
    <div className="page">
      <NotificationCenter />
      <header className="topbar">
        <h1>AI Agentic Platform</h1>
        <div className="topbar-menus">
          {token && (
            <>
              <Link className="menu-link" to="/dashboard" onClick={closeMenus}>
                Dashboard
              </Link>

              <Link className="menu-link" to="/articles" onClick={closeMenus}>
                Articles
              </Link>

              <div className="menu-group">
                <button className="menu-trigger" type="button" onClick={() => toggleMenu("users")}>
                  Users
                </button>
                {openMenu === "users" && (
                  <div className="submenu">
                    <Link className="submenu-item" to="/users" onClick={closeMenus}>
                      Manage Users
                    </Link>
                    <Link className="submenu-item" to="/profile" onClick={closeMenus}>
                      Profile
                    </Link>
                    <button className="submenu-item submenu-item-danger" onClick={handleLogout} type="button">
                      Logout
                    </button>
                  </div>
                )}
              </div>

              <div className="menu-group">
                <button className="menu-trigger" type="button" onClick={() => toggleMenu("agents")}>
                  Agents
                </button>
                {openMenu === "agents" && (
                  <div className="submenu">
                    <Link className="submenu-item" to="/agents" onClick={closeMenus}>
                      Manage Agents
                    </Link>
                    <Link className="submenu-item" to="/agents-chat" onClick={closeMenus}>
                      Agents Chat
                    </Link>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}
