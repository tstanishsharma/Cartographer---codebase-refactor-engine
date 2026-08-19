import { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@utils/cn'

interface EmptyStateProps {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className={cn(
        'flex flex-col items-center justify-center p-12 text-center rounded-xl border border-dashed border-border/60 bg-card/20',
        className
      )}
    >
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-secondary text-primary/80 mb-6 shadow-inner ring-1 ring-white/5">
        {icon}
      </div>
      <h3 className="mb-2 text-xl font-semibold tracking-tight text-foreground">
        {title}
      </h3>
      <p className="mb-6 max-w-sm text-sm text-muted-foreground leading-relaxed">
        {description}
      </p>
      {action && <div>{action}</div>}
    </motion.div>
  )
}
