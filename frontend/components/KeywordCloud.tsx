interface KeywordCloudProps {
  keywords: { keyword: string; count: number }[]
}

export function KeywordCloud({ keywords }: KeywordCloudProps) {
  if (!keywords || keywords.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        키워드 데이터가 없습니다
      </div>
    )
  }

  const maxCount = Math.max(...keywords.map(k => k.count))

  return (
    <div className="space-y-3">
      {keywords.slice(0, 8).map((item, index) => {
        const percentage = (item.count / maxCount) * 100

        return (
          <div key={index} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-gray-700 font-medium">{item.keyword}</span>
              <span className="text-gray-400">{item.count}</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-primary-400 to-primary-600 rounded-full transition-all duration-500"
                style={{ width: `${percentage}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
