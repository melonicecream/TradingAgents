'use client'

interface ProgressPanelProps {
  progress: {
    step: number
    total: number
    progress: number
    elapsed_seconds?: number
    agent: string | null
    current_stage: string | null
    agent_status: Record<string, string>
    milestone_status: Record<string, string>
    completed_milestones: number
    total_milestones: number
    reports: Record<string, string>
  }
}

export function ProgressPanel({ progress }: ProgressPanelProps) {
  const agentEntries = Object.entries(progress.agent_status)
  const completedAgents = agentEntries.filter(([_, status]) => status === 'completed').length
  const totalAgents = agentEntries.length || progress.total

  const milestoneEntries = Object.entries(progress.milestone_status)
  const completedMilestones = milestoneEntries.filter(([, status]) => status === 'completed').length

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          분석 진행 중
        </h3>
        <span className="text-sm text-gray-500">
          {Math.round(progress.progress)}%
        </span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
          style={{ width: `${progress.progress}%` }}
        />
      </div>

      {progress.current_stage && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="text-sm text-blue-600 font-medium">
            현재 단계
          </div>
          <div className="text-lg font-semibold text-blue-900">
            {progress.current_stage}
          </div>
        </div>
      )}

      <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-lg">
        <div className="text-sm text-slate-600 font-medium">
          마일스톤 진행률
        </div>
        <div className="text-lg font-semibold text-slate-900">
          {completedMilestones}/{progress.total_milestones}
        </div>
        {typeof progress.elapsed_seconds === 'number' && (
          <div className="mt-1 text-xs text-slate-500">
            경과 시간 {formatDuration(progress.elapsed_seconds)}
          </div>
        )}
      </div>

      <div className="space-y-2 mb-4">
        <h4 className="text-sm font-medium text-gray-700 mb-2">
          실행 단계
        </h4>
        <div className="grid grid-cols-2 gap-2">
          {milestoneEntries.map(([stageName, status]) => {
            const isCompleted = status === 'completed'
            const isCurrent = progress.current_stage === stageName

            return (
              <div
                key={stageName}
                className={`flex items-center gap-2 p-2 rounded-lg text-sm ${
                  isCompleted
                    ? 'bg-green-50 text-green-700'
                    : isCurrent
                    ? 'bg-blue-50 text-blue-700 border border-blue-200'
                    : 'bg-gray-50 text-gray-500'
                }`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    isCompleted
                      ? 'bg-green-500'
                      : isCurrent
                      ? 'bg-blue-500 animate-pulse'
                      : 'bg-gray-300'
                  }`}
                />
                <span className="truncate">{stageName}</span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-700 mb-2">
          에이전트 상태 ({completedAgents}/{totalAgents})
        </h4>
        <div className="grid grid-cols-2 gap-2">
          {agentEntries.map(([agentName, status]) => {
            const isCompleted = status === 'completed'
            const isCurrent = progress.agent === agentName

            return (
              <div
                key={agentName}
                className={`flex items-center gap-2 p-2 rounded-lg text-sm ${
                  isCompleted
                    ? 'bg-green-50 text-green-700'
                    : isCurrent
                    ? 'bg-blue-50 text-blue-700 border border-blue-200'
                    : 'bg-gray-50 text-gray-500'
                }`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    isCompleted
                      ? 'bg-green-500'
                      : isCurrent
                      ? 'bg-blue-500 animate-pulse'
                      : 'bg-gray-300'
                  }`}
                />
                <span className="truncate">{agentName}</span>
              </div>
            )
          })}
        </div>
      </div>

      {Object.keys(progress.reports).length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            완료된 보고서
          </h4>
          <div className="flex flex-wrap gap-2">
            {Object.entries(progress.reports).map(([key, status]) => (
              <span
                key={key}
                className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full"
              >
                {key === 'market_report' && '시장 분석'}
                {key === 'sentiment_report' && '감성 분석'}
                {key === 'news_report' && '뉴스 분석'}
                {key === 'fundamentals_report' && '펀더멘털 분석'}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function formatDuration(totalSeconds: number) {
  const roundedSeconds = Math.max(Math.round(totalSeconds), 0)
  const minutes = Math.floor(roundedSeconds / 60)
  const seconds = roundedSeconds % 60

  if (minutes === 0) {
    return `${seconds}초`
  }

  return `${minutes}분 ${seconds}초`
}
