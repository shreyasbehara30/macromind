import type { Metadata } from "next";
import { Geist, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Providers from "./providers";
import AuthProvider from "@/components/AuthProvider";
import PageTransition from "@/components/PageTransition";
import MainLayoutWrapper from "@/components/MainLayoutWrapper";
import { Toaster } from "react-hot-toast";

const geist = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MacroMind | Financial Intelligence",
  description: "AI-agentic fintech platform",
  manifest: "/manifest.json"
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
      </head>
      <body className="antialiased bg-bg-primary text-text-primary h-screen overflow-hidden">
        <Providers>
          <AuthProvider>
            <MainLayoutWrapper>
              <PageTransition>
                {children}
              </PageTransition>
            </MainLayoutWrapper>
            <Toaster position="bottom-right" toastOptions={{
              style: {
                background: '#1E222D',
                color: '#D1D4DC',
                border: '1px solid #363A45',
              }
            }} />
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
