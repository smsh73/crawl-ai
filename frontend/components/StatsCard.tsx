import { ReactNode } from 'react'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface StatsCardProps {
  title: string
  value: number | string
  icon: ReactNode
  color: 'blue' | 'green' | 'emerald' | 'purple' | 'red' | 'yellow'
  trend?: string
}

const colorClasses = {
  blue: 'bg-blue-50 text-blue-600',
  green: 'bg-green-50 text-green-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  purple: 'bg-purple-50 text-purple-600',
  red: 'bg-red-50 text-red-600',
  yellow: 'bg-yellow-50 text-yellow-600',
}

export function StatsCard({ title, value, icon, color, trend }: StatsCardProps) {
  const isPositive = trend?.startsWith('+')

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 card-hover">
      <div className="flex items-center justify-between">
        <div className={`p-3 rounded-xl ${colorClasses[color]}`}>
          {icon}
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-sm ${
            isPositive ? 'text-green-600' : 'text-red-600'
          }`}>
            {isPositive ? (
              <TrendingUp className="w-4 h-4" />
            ) : (
              <TrendingDown className="w-4 h-4" />
            )}
            {trend}
          </div>
        )}
      </div>
      <div className="mt-4">
        <h3 className="text-sm text-gray-500">{title}</h3>
        <p className="text-2xl font-bold text-gray-900 mt-1">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </p>
      </div>
    </div>
  )
}
