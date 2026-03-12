interface EmptyStateProps {
  title: string;
  description?: string;
  action?: {
    label: string;
    href: string;
  };
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="text-center py-16">
      <h3 className="text-sm font-medium text-foreground mb-1">{title}</h3>
      {description && <p className="text-sm text-muted mb-4">{description}</p>}
      {action && (
        <a
          href={action.href}
          className="inline-flex items-center px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-blue-600 transition-colors"
        >
          {action.label}
        </a>
      )}
    </div>
  );
}
