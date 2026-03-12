const STAGES = ["searching", "scoring", "enriching", "drafting", "complete"];

interface PipelineProgressProps {
  currentStage: string;
}

export function PipelineProgress({ currentStage }: PipelineProgressProps) {
  const currentIndex = STAGES.indexOf(currentStage);
  const isFailed = currentStage === "failed";
  const isIdle = currentStage === "idle";

  return (
    <div className="flex items-center gap-1">
      {STAGES.map((stage, i) => {
        let dotClass = "w-2.5 h-2.5 rounded-full ";
        if (isFailed) {
          dotClass += "bg-red-300";
        } else if (isIdle) {
          dotClass += "bg-gray-200";
        } else if (i < currentIndex) {
          dotClass += "bg-green-500";
        } else if (i === currentIndex) {
          dotClass += "bg-blue-500";
        } else {
          dotClass += "bg-gray-200";
        }

        return (
          <div key={stage} className="flex items-center gap-1">
            <div className={dotClass} title={stage} />
            {i < STAGES.length - 1 && (
              <div className={`w-4 h-0.5 ${i < currentIndex ? "bg-green-300" : "bg-gray-200"}`} />
            )}
          </div>
        );
      })}
      <span className="ml-2 text-xs text-muted capitalize">
        {isFailed ? "Failed" : isIdle ? "Not started" : currentStage}
      </span>
    </div>
  );
}
