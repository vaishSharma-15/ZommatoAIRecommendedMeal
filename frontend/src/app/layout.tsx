import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Zomoto AI - Restaurant Recommendations",
  description: "AI-powered restaurant recommendations based on your preferences",
  keywords: ["restaurant", "recommendations", "AI", "food", "dining"],
  authors: [{ name: "Zomoto AI Team" }],
  creator: "Zomoto AI Team",
  publisher: "Zomoto AI",
  formatDetection: { email: false },
  metadataBase: new URL("https://zomoto.ai"),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://zomoto.ai",
    title: "Zomoto AI - Restaurant Recommendations",
    description: "AI-powered restaurant recommendations based on your preferences",
    siteName: "Zomoto AI",
  },
  twitter: {
    card: "summary_large_image",
    title: "Zomoto AI - Restaurant Recommendations",
    description: "AI-powered restaurant recommendations based on your preferences",
    creator: "@zomotoai",
    site: "@zomotoai",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
      </body>
    </html>
  );
}
