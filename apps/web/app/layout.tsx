import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "小提琴旋律谱",
  description: "把清晰的旋律录音转换成可编辑的小提琴练习谱。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
