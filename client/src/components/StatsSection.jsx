function StatsSection({ stats }) {
  return (
    <div className="stats-grid">
      {stats.map((item, index) => (
        <div key={index} className="stats-card">
          <p>{item.title}</p>
          <h2>{item.value}</h2>
          {item.subtitle && (
            <small>{item.subtitle}</small>
          )}
        </div>
      ))}
    </div>
  );
}

export default StatsSection;