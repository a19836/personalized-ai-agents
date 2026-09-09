import { useNotifications } from "../shared/notifications";

export default function NotificationCenter() {
  const { items, dismiss } = useNotifications();
  if (!items.length) return null;

  return (
    <div className="notification-center" role="status" aria-live="polite" aria-atomic="true">
      {items.map((item) => (
        <div key={item.id} className={`notification-toast ${item.type}`}>
          <span>{item.message}</span>
          <button
            type="button"
            className="notification-close"
            aria-label="Close notification"
            onClick={() => dismiss(item.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

