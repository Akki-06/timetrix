function StatsSection({ stats }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
        gap: "20px",
      }}
    >
      {stats.map((item, index) => (
        <div
          key={index}
          style={{
            background: "#ffffff",
            padding: "20px",
            borderRadius: "12px",
            boxShadow: "0 2px 6px rgba(0,0,0,0.05)",
          }}
        >
          <p style={{ color: "#6b7280", marginBottom: "8px" }}>
            {item.title}
          </p>
          <h2 style={{ margin: 0 }}>{item.value}</h2>
          {item.subtitle && (
            <small style={{ color: "#6b7280" }}>{item.subtitle}</small>
          )}
        </div>
      ))}
    </div>
  );
}

export default StatsSection;