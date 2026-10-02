import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BLR Real Estate Sales Analysis",
  description: "Bengaluru Urban and Rural Karnataka RERA sales, complaints, and survey-number case search",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,680&family=Sora:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>{children}</body>
    </html>
  );
}
