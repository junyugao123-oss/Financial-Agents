import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "君宇·投研智能体",
  description: "顶级基金决策室，还原专业金融机构投研团队的完整决策流程。",
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
