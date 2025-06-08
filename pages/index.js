import { useEffect } from "react";

export default function Home() {
  useEffect(() => {
    window.location.href = "/index.html";
  }, []);

  return null; // lub loading spinner
}