function TermStatusSection({ term }) {
  return (
    <div className="panel-card">
      <h3>Current Term Status</h3>

      <div className="term-list">
        <p><strong>Term:</strong> {term.name}</p>
        <p><strong>Status:</strong> {term.status}</p>
        <p><strong>Courses:</strong> {term.courses}</p>
        <p><strong>Student Groups:</strong> {term.groups}</p>
        <p><strong>Offerings:</strong> {term.offerings}</p>
      </div>

      <div className="progress-wrap">
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: `${term.progress}%` }}
          />
        </div>
        <small>{term.progress}% Complete</small>
      </div>
    </div>
  );
}

export default TermStatusSection;