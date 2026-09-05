import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { SessionNav } from "@/components/SessionNav";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "IntentGuard",
  description:
    "Authorization layer for AI agents. Agents may propose. IntentGuard decides whether they may pay.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} antialiased`}
    >
      <body className="min-h-[100dvh] bg-canvas font-sans text-ink">
        <SessionNav />
        <div className="mx-auto w-full max-w-[1400px] px-4 pb-16 pt-8 md:px-8">
          {children}
        </div>
      </body>
    </html>
  );
}
