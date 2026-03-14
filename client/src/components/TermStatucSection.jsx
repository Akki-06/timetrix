function TermStatusSection({ term }) {
  return (
    <div
      style={{
        background: "#ffffff",
        padding: "20px",
        borderRadius: "12px",
        boxShadow: "0 2px 6px rgba(0,0,0,0.05)",
      }}
    >
      <h3 style={{ marginBottom: "16px" }}>Current Term Status</h3>

      <p><strong>Term:</strong> {term.name}</p>
      <p><strong>Status:</strong> {term.status}</p>
      <p><strong>Courses:</strong> {term.courses}</p>
      <p><strong>Student Groups:</strong> {term.groups}</p>
      <p><strong>Offerings:</strong> {term.offerings}</p>

      <div style={{ marginTop: "16px" }}>
        <div
          style={{
            height: "8px",
            background: "#e5e7eb",
            borderRadius: "6px",
          }}
        >
          <div
            style={{
              width: `${term.progress}%`,
              height: "8px",
              background: "#3b82f6",
              borderRadius: "6px",
            }}
          />
        </div>
        <small>{term.progress}% Complete</small>
      </div>
    </div>
  );
}

export default TermStatusSection;