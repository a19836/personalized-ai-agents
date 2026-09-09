import { Link, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./modules/auth/page";
import { ArticlesPage, CreateArticlePage, EditArticlePage } from "./modules/articles/page";
import { ProfilePage, UsersManagementPage } from "./modules/users/page";
import { AgentsChatPage, AgentsManagePage } from "./modules/agents/page";

function DashboardPage() {
  return (
    <Layout>
      <section className="cards-grid">
        <article className="card panel">
          <h2>Login Panel</h2>
          <p>Manage your authenticated session with Firebase JWT.</p>
          <Link to="/profile" className="button-link">
            View Current User
          </Link>
        </article>
        <article className="card panel">
          <h2>List Articles Panel</h2>
          <p>Browse all articles with creation/update dates.</p>
          <Link to="/articles" className="button-link">
            Open Articles
          </Link>
        </article>
        <article className="card panel">
          <h2>Manage Agents Panel</h2>
          <p>Create, deploy, and manage your own AI agents.</p>
          <Link to="/agents" className="button-link">
            Open Manage Agents
          </Link>
        </article>
        <article className="card panel">
          <h2>Agents Chat Panel</h2>
          <p>Chat with your deployed agents and legacy agents.</p>
          <Link to="/agents-chat" className="button-link">
            Open Agents Chat
          </Link>
        </article>
        <article className="card panel">
          <h2>Users Management Panel</h2>
          <p>List application users, edit user profile fields, or delete users.</p>
          <Link to="/users" className="button-link">
            Open Users Management
          </Link>
        </article>
      </section>
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/articles"
        element={
          <ProtectedRoute>
            <ArticlesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/articles/new"
        element={
          <ProtectedRoute>
            <CreateArticlePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/articles/:articleId"
        element={
          <ProtectedRoute>
            <EditArticlePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/agents"
        element={
          <ProtectedRoute>
            <AgentsManagePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/agents-chat"
        element={
          <ProtectedRoute>
            <AgentsChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/users"
        element={
          <ProtectedRoute>
            <UsersManagementPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
