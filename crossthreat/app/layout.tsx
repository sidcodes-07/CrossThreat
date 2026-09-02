import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrossThreat",
  description: "Cyber threat forecasting analyst console",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-[#050b17] text-zinc-100">{children}</body>
    </html>
  );
}
