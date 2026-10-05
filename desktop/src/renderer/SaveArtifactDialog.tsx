import { useRef, useState } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { Button } from "./components/ui/button";

export function SaveArtifactDialog({ label, fileName, returnFocus, onSave, onCancel }: {
  label: string; fileName: string; returnFocus: HTMLElement | null; onSave: (path: string) => Promise<void>; onCancel: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [path, setPath] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return <Dialog.Root open disablePointerDismissal={saving} onOpenChange={(open, event) => {
    if (!open) { if (saving) event.cancel(); else onCancel(); }
  }}>
    <Dialog.Portal>
      <Dialog.Backdrop className="fixed inset-0 z-50 bg-black/40" />
      <Dialog.Popup initialFocus={input} finalFocus={() => returnFocus}
        className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-base border-2 border-border bg-secondary-background p-6 shadow-shadow">
        <Dialog.Title className="text-xl font-semibold">{label} 저장</Dialog.Title>
        <Dialog.Description className="detail-note">저장할 파일의 절대 경로를 입력하세요. 같은 이름의 파일이 있으면 덮어씁니다.</Dialog.Description>
        <form className="space-y-4" onSubmit={(event) => {
          event.preventDefault();
          if (saving || !path.trim()) return;
          setSaving(true); setError(null);
          void onSave(path).catch(() => {
            setError("저장하지 못했습니다. 파일의 절대 경로와 폴더 존재 여부, 쓰기 권한을 확인해 주세요. 앱 데이터 폴더에는 저장할 수 없습니다.");
          }).finally(() => setSaving(false));
        }}>
          <div className="field">
            <label htmlFor="artifact-save-path">저장 파일 경로</label>
            <input ref={input} id="artifact-save-path" type="text" required maxLength={4096} value={path} disabled={saving}
              placeholder={`C:\\Users\\이름\\Documents\\${fileName} 또는 /Users/name/Documents/${fileName}`}
              onChange={(event) => { setPath(event.target.value); setError(null); }}
              aria-describedby="artifact-save-error"
              className="w-full rounded-base border-2 border-border bg-secondary-background px-3 py-2 text-sm disabled:opacity-50" />
          </div>
          <div id="artifact-save-error">{error && <p className="detail-note" role="alert">{error}</p>}</div>
          <div className="action-row justify-end">
            <Dialog.Close disabled={saving} render={<Button type="button" variant="outline" />}>취소</Dialog.Close>
            <Button type="submit" disabled={saving || !path.trim()}>{saving ? "저장 중…" : "저장"}</Button>
          </div>
        </form>
      </Dialog.Popup>
    </Dialog.Portal>
  </Dialog.Root>;
}
