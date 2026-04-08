'use client'

import { useState } from 'react'

const ANALYSTS = [
  { id: 'market', name: '시장 분석가', description: '기술적 지표 분석' },
  { id: 'social', name: '소셜 미디어', description: '감성 분석' },
  { id: 'news', name: '뉴스 분석가', description: '뉴스 및 매크로' },
  { id: 'fundamentals', name: '펀더멘털', description: '재무제표 분석' },
]

interface AnalysisFormProps {
  onSubmit: (ticker: string, date: string, analysts: string[]) => void
  isLoading: boolean
}

export function AnalysisForm({ onSubmit, isLoading }: AnalysisFormProps) {
  const [ticker, setTicker] = useState('005930.KS')
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])
  const [selectedAnalysts, setSelectedAnalysts] = useState<string[]>(['market', 'social', 'news', 'fundamentals'])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(ticker, date, selectedAnalysts)
  }

  const toggleAnalyst = (id: string) => {
    setSelectedAnalysts(prev => 
      prev.includes(id) 
        ? prev.filter(a => a !== id)
        : [...prev, id]
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        분석 설정
      </h2>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            종목 코드
          </label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="005930.KS"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={isLoading}
          />
          <p className="mt-1 text-xs text-gray-500">
            예: 005930.KS (삼성전자), AAPL, TSLA
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            분석 날짜
          </label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={isLoading}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            분석가 선택
          </label>
          <div className="space-y-2">
            {ANALYSTS.map((analyst) => (
              <label
                key={analyst.id}
                className="flex items-center p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedAnalysts.includes(analyst.id)}
                  onChange={() => toggleAnalyst(analyst.id)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  disabled={isLoading}
                />
                <div className="ml-3">
                  <div className="text-sm font-medium text-gray-900">
                    {analyst.name}
                  </div>
                  <div className="text-xs text-gray-500">
                    {analyst.description}
                  </div>
                </div>
              </label>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading || selectedAnalysts.length === 0}
          className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              분석 중...
            </span>
          ) : (
            '분석 시작'
          )}
        </button>
      </form>
    </div>
  )
}
