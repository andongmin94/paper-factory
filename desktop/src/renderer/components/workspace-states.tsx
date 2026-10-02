import { ArrowRight, BookOpen, LoaderCircle, Sparkles } from "lucide-react";
import { Button } from "./ui/button";

export function Empty({
  icon,
  title,
  description,
  onStart,
}: {
  icon: "progress" | "library";
  title: string;
  description: string;
  onStart?: () => void;
}) {
  const Icon = icon === "library" ? BookOpen : Sparkles;
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={38} />
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {onStart && (
        <Button onClick={onStart}>
          첫 연구 시작하기
          <ArrowRight size={16} />
        </Button>
      )}
    </div>
  );
}
export function Loading() {
  return (
    <p className="loading-state" role="status">
      <LoaderCircle className="spinner" size={20} />
      작업실의 기록을 불러오고 있습니다.
    </p>
  );
}
