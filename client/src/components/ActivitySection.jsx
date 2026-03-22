function ActivitySection({ activities }) {
  return (
    <div className="panel-card">
      <h3>Recent Activity</h3>

      {activities.map((item, index) => (
        <div key={index} className="activity-item">
          <div className="activity-dot-wrap">
            <span
              className="activity-dot"
              style={{
                background: item.type === "error" ? "var(--danger)" : "var(--success)",
              }}
            />
          </div>
          <div className="activity-body">
            <div className="activity-title">{item.title || item.message}</div>
            {item.description && (
              <div className="activity-desc">{item.description}</div>
            )}
            <small className="activity-time">{item.time}</small>
          </div>
        </div>
      ))}
    </div>
  );
}

export default ActivitySection;
