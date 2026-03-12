import type { Metadata } from "next";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI SDR OS",
  description: "AI-powered lead generation and outreach platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <Sidebar />
        <main className="ml-60 min-h-screen p-8">
          <div className="max-w-6xl mx-auto">{children}</div>
        </main>
      </body>
    </html>
  );
}
