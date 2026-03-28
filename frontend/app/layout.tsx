import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KisanMind - AI Agricultural Advisory",
  description:
    "Satellite-powered, multilingual agricultural advisory system for Indian farmers",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="hi"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {/* Header */}
        <header className="sticky top-0 z-50 border-b border-white/5 bg-kisan-dark/80 backdrop-blur-xl">
          <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5">
              <span className="text-2xl">🌾</span>
              <span className="text-xl font-bold tracking-tight">
                <span className="gradient-text">KisanMind</span>
              </span>
              <span className="hidden text-sm text-white/40 sm:inline">
                | किसानमाइंड
              </span>
            </Link>

            <nav className="hidden items-center gap-1 md:flex">
              <Link
                href="/"
                className="rounded-lg px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white"
              >
                Dashboard
              </Link>
              <Link
                href="/mandi"
                className="rounded-lg px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white"
              >
                Mandi Prices
              </Link>
              <Link
                href="/weather"
                className="rounded-lg px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white"
              >
                Weather
              </Link>
            </nav>

            <div className="flex items-center gap-3">
              <span className="rounded-full bg-white/5 px-3 py-1.5 text-xs font-medium text-white/60">
                🛰️ Live
              </span>
            </div>
          </div>
        </header>

        {/* Main */}
        <main className="flex-1 grid-bg">{children}</main>

        {/* Footer */}
        <footer className="border-t border-white/5 bg-kisan-dark py-6">
          <div className="mx-auto max-w-7xl px-4 text-center text-xs text-white/30">
            KisanMind -- AI-Powered Agricultural Advisory | Built for ET GenAI Hackathon 2026
          </div>
        </footer>
      </body>
    </html>
  );
}
