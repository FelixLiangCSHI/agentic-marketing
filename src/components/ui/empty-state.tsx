import { Icon, type IconName } from "@/components/ui/icon";

interface EmptyStateProps {
  icon?: IconName;
  title: string;
  description: string;
}

export function EmptyState({
  icon = "table",
  title,
  description,
}: EmptyStateProps) {
  return (
    <div className="empty-state" role="status">
      <span className="empty-state__icon">
        <Icon name={icon} size={24} />
      </span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}
