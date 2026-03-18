import { useRef, useState } from "react";
import api from "../api/axios";
import {
  downloadTemplateFile,
  normalizeRowKeys,
  readSpreadsheetRows,
} from "../utils/spreadsheet";

function formatApiError(error) {
  if (error?.response?.data) {
    if (typeof error.response.data === "string") return error.response.data;
    return JSON.stringify(error.response.data);
  }

  if (error instanceof Error) return error.message;
  return "Unknown upload error";
}

function BulkUploadCard({
  title,
  endpoint,
  requiredColumns,
  mapRow,
  onUploadComplete,
  helperText,
  templateFileName,
  templateSampleRow,
}) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const uploadFile = async (selectedFile) => {
    if (!selectedFile || isUploading) return;

    setIsUploading(true);
    setResult(null);

    try {
      const rows = await readSpreadsheetRows(selectedFile);
      if (!rows.length) {
        setResult({ type: "error", message: "File is empty." });
        return;
      }

      const normalizedRows = rows.map(normalizeRowKeys);
      const headers = Object.keys(normalizedRows[0]);
      const missingColumns = requiredColumns.filter(
        (col) => !headers.includes(col)
      );

      if (missingColumns.length) {
        setResult({
          type: "error",
          message: `Missing columns: ${missingColumns.join(", ")}`,
        });
        return;
      }

      let successCount = 0;
      const failedRows = [];

      for (let i = 0; i < normalizedRows.length; i += 1) {
        const row = normalizedRows[i];
        try {
          const payload = mapRow(row, i + 2);
          await api.post(endpoint, payload);
          successCount += 1;
        } catch (error) {
          failedRows.push({
            row: i + 2,
            error: formatApiError(error),
          });
        }
      }

      setResult({
        type: failedRows.length ? "partial" : "success",
        successCount,
        failedRows,
      });
      setFile(null);

      if (onUploadComplete) onUploadComplete();
    } catch (error) {
      setResult({ type: "error", message: formatApiError(error) });
    } finally {
      setIsUploading(false);
    }
  };

  const handleUploadClick = () => {
    if (isUploading) return;

    if (file) {
      uploadFile(file);
      return;
    }

    fileInputRef.current?.click();
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    setFile(selectedFile);
    if (selectedFile) {
      uploadFile(selectedFile);
    }
  };

  const handleTemplateDownload = () => {
    downloadTemplateFile({
      headers: requiredColumns,
      sampleRow: templateSampleRow,
      fileName: templateFileName || `${title.toLowerCase().replace(/\s+/g, "-")}-template.xlsx`,
    });
  };

  return (
    <section className="upload-card">
      <h3>{title}</h3>
      {helperText ? <p className="upload-help">{helperText}</p> : null}

      <div className="upload-actions">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFileChange}
          style={{ display: "none" }}
        />
        <button
          type="button"
          className="btn-secondary"
          onClick={handleTemplateDownload}
        >
          Download Template
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={handleUploadClick}
          disabled={isUploading}
        >
          {isUploading ? "Uploading..." : file ? "Upload Selected File" : "Upload Excel/CSV"}
        </button>
      </div>

      {file ? <p className="upload-help">Selected: {file.name}</p> : null}

      {result?.type === "error" ? (
        <p className="upload-error">{result.message}</p>
      ) : null}

      {result?.type === "success" ? (
        <p className="upload-success">
          Uploaded {result.successCount} rows successfully.
        </p>
      ) : null}

      {result?.type === "partial" ? (
        <div className="upload-partial">
          <p className="upload-success">
            Uploaded {result.successCount} rows. Failed {result.failedRows.length}
            rows.
          </p>
          <ul>
            {result.failedRows.slice(0, 5).map((item) => (
              <li key={`${item.row}-${item.error}`}>
                Row {item.row}: {item.error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export default BulkUploadCard;
