import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MelodySheet Violin",
  description: "Turn a clear melody recording into an editable violin practice sheet.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
