function ActivitySection({ activities }) {
  return (
    <div className="panel-card">
      <h3>Recent Activity</h3>

      {activities.map((item, index) => (
        <div key={index} className="activity-item">
          <div className="activity-message">{item.message}</div>
          <small>{item.time}</small>
        </div>
      ))}
    </div>
  );
}

export default ActivitySection;