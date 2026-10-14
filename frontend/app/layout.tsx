import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "../components/Sidebar";
import TopBar from "../components/TopBar";

export const metadata: Metadata = {
  title: "TubeForge AI",
  description: "Private AI-powered YouTube operating system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-studio-bg text-studio-text font-sans antialiased">
        <Sidebar />
        <div className="pl-60 min-h-screen flex flex-col">
          <TopBar />
          <main className="flex-1 px-6 py-6 max-w-[1600px] w-full mx-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
