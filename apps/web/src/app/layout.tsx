import type { Metadata } from "next";
import { Geist, Geist_Mono, Bebas_Neue } from "next/font/google";
import "./globals.css";
import AppFooter from "@/components/AppFooter";
import CookieBanner from "@/components/legal/CookieBanner";
// import AppHeaderLegal from "@/components/AppHeaderLegal";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const bebasNeue = Bebas_Neue({
  weight: "400",
  variable: "--font-bebas-neue",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "See the shift before the move",
  description:
    "Institutional-grade regime intelligence across markets and earnings. Track regime shifts and instability — deterministic, explainable, stress-aware.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${bebasNeue.variable} antialiased`}
      >
        {/* Cookie consent banner (QC-safe defaults) */}
        <CookieBanner />
        {/* Optional: a simple legal-links header everywhere */}
        {/* <AppHeaderLegal /> */}

        {children}
        <AppFooter />
      </body>
    </html>
  );
}
