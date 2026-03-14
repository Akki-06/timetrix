function ActivitySection({ activities }) {
  return (
    <div
      style={{
        background: "#ffffff",
        padding: "20px",
        borderRadius: "12px",
        boxShadow: "0 2px 6px rgba(0,0,0,0.05)",
      }}
    >
      <h3 style={{ marginBottom: "16px" }}>Recent Activity</h3>

      {activities.map((item, index) => (
        <div
          key={index}
          style={{
            padding: "10px 0",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <div>{item.message}</div>
          <small style={{ color: "#6b7280" }}>{item.time}</small>
        </div>
      ))}
    </div>
  );
}

export default ActivitySection;