'use client'

import { useState, useEffect } from 'react'

interface HistoryItem {
  id: number
  ticker: string
  analysis_date: string
  decision: string
  full_decision?: string
  created_at: string
}

export function HistoryPanel() {
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

  const fetchHistory = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/history?page=${page}&page_size=10`)
      const data = await res.json()
      setHistory(data.items || [])
      setTotalPages(data.pages || 1)
    } catch (err) {
      console.error('Failed to fetch history:', err)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchHistory()
  }, [page])

  const getDecisionColor = (decision: string) => {
    const colors: Record<string, string> = {
      'Buy': 'bg-green-100 text-green-700',
      'Overweight': 'bg-lime-100 text-lime-700',
      'Hold': 'bg-yellow-100 text-yellow-700',
      'Underweight': 'bg-orange-100 text-orange-700',
      'Sell': 'bg-red-100 text-red-700',
    }
    return colors[decision] || 'bg-gray-100 text-gray-700'
  }

  const getDecisionLabel = (decision: string) => {
    const labels: Record<string, string> = {
      'Buy': '매수',
      'Overweight': '비중 확대',
      'Hold': '보유',
      'Underweight': '비중 축소',
      'Sell': '매도',
    }
    return labels[decision] || decision
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          분석 이력
        </h3>
        <button
          onClick={fetchHistory}
          disabled={loading}
          className="text-sm text-blue-600 hover:text-blue-700 disabled:opacity-50"
        >
          {loading ? '로딩...' : '새로고침'}
        </button>
      </div>

      {history.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          아직 분석 이력이 없습니다.
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {history.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-3 border border-gray-100 rounded-lg hover:bg-gray-50"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-700 font-bold">
                    {item.ticker.slice(0, 2)}
                  </div>
                  <div>
                    <div className="font-medium text-gray-900">{item.ticker}</div>
                    <div className="text-sm text-gray-500">
                      {new Date(item.created_at).toLocaleDateString('ko-KR')}
                    </div>
                  </div>
                </div>
                <div className={`px-3 py-1 rounded-full text-sm font-medium ${getDecisionColor(item.decision)}`}>
                  {getDecisionLabel(item.decision)}
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                이전
              </button>
              <span className="text-sm text-gray-600">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 border rounded disabled:opacity-50"
              >
                다음
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
