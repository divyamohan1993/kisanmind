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

            <nav className="hidden items-center gap-0.5 md:flex">
              <Link
                href="/talk"
                className="rounded-lg bg-healthy/10 border border-healthy/20 px-3 py-1.5 text-xs font-semibold text-healthy transition-colors hover:bg-healthy/20"
              >
                Farmer Mode
              </Link>
              <Link
                href="/"
                className="rounded-lg px-2.5 py-1.5 text-xs text-white/60 transition-colors hover:bg-white/5 hover:text-white"
              >
                Dashboard
              </Link>
              <Link
                href="/demo"
                className="rounded-lg px-2.5 py-1.5 text-xs text-white/60 transition-colors hover:bg-white/5 hover:text-white"
              >
                Demo
              </Link>
              <Link
                href="/mandi"
                className="rounded-lg px-2.5 py-1.5 text-xs text-white/60 transition-colors hover:bg-white/5 hover:text-white"
              >
                Mandi
              </Link>
              <Link
                href="/weather"
                className="rounded-lg px-2.5 py-1.5 text-xs text-white/60 transition-colors hover:bg-white/5 hover:text-white"
              >
                Weather
              </Link>
            </nav>

            <div className="flex items-center gap-3">
              <Link
                href="/talk"
                className="md:hidden flex items-center gap-1 rounded-full bg-healthy/20 border border-healthy/30 px-3 py-1.5 text-xs font-medium text-healthy"
              >
                Voice
              </Link>
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-healthy/5 border border-healthy/20 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-healthy">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-healthy opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-healthy" />
                </span>
                Live
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
