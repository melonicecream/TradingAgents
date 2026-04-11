import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TradingAgents - AI 주식 분석',
  description: '다중 에이전트 AI 기반 주식 분석 플랫폼',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <body className="antialiased bg-gray-50">{children}</body>
    </html>
  )
}
