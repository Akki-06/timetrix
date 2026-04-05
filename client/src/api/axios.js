import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/",
  timeout: 600000, // 10 minutes — scheduler can take time on large datasets
});

export default api;