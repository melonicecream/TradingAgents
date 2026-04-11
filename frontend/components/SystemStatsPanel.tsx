'use client'

export interface SystemStats {
  concurrent_runs: number
  running_executions: number
  resumable_executions: number
  failed_executions: number
  completed_executions: number
  total_executions: number
  active_leases: number
}

interface SystemStatsPanelProps {
  stats: SystemStats | null
  isLoading: boolean
}

const STAT_CARDS = [
  {
    key: 'concurrent_runs',
    label: '동시 실행',
    valueClassName: 'text-indigo-700',
    blockClassName: 'bg-indigo-50 border-indigo-100',
  },
  {
    key: 'running_executions',
    label: '실행 중',
    valueClassName: 'text-blue-700',
    blockClassName: 'bg-blue-50 border-blue-100',
  },
  {
    key: 'completed_executions',
    label: '완료',
    valueClassName: 'text-green-700',
    blockClassName: 'bg-green-50 border-green-100',
  },
  {
    key: 'resumable_executions',
    label: '재개 가능',
    valueClassName: 'text-amber-700',
    blockClassName: 'bg-amber-50 border-amber-100',
  },
  {
    key: 'failed_executions',
    label: '실패',
    valueClassName: 'text-red-700',
    blockClassName: 'bg-red-50 border-red-100',
  },
  {
    key: 'active_leases',
    label: '활성 Lease',
    valueClassName: 'text-slate-700',
    blockClassName: 'bg-slate-50 border-slate-100',
  },
  {
    key: 'total_executions',
    label: '전체 실행 수',
    valueClassName: 'text-gray-900',
    blockClassName: 'bg-gray-50 border-gray-100',
  },
] as const

export function SystemStatsPanel({ stats, isLoading }: SystemStatsPanelProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          시스템 현황
        </h3>
        <span className="text-xs text-gray-500">
          실시간 실행 통계
        </span>
      </div>

      {isLoading && !stats ? (
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-sm text-gray-500">
          시스템 통계를 불러오는 중입니다...
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          {STAT_CARDS.map((card) => (
            <div
              key={card.key}
              className={`rounded-lg border p-4 ${card.blockClassName}`}
            >
              <div className="text-xs font-medium text-gray-500 mb-1">
                {card.label}
              </div>
              <div className={`text-2xl font-bold ${card.valueClassName}`}>
                {stats[card.key]}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 text-sm text-gray-500">
          시스템 통계를 아직 표시할 수 없습니다.
        </div>
      )}
    </div>
  )
}
