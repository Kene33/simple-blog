const URL_PATTERN = /(https?:\/\/[^\s]+|www\.[^\s]+)/gi;

export function LinkifiedText({ children }) {
  const text = String(children || "");
  return text.split(URL_PATTERN).map((part, index) => {
    if (!/^https?:\/\//i.test(part) && !/^www\./i.test(part)) return part;
    const clean = part.replace(/[),.!?;:]+$/, "");
    const trailing = part.slice(clean.length);
    return <span key={`${part}-${index}`}><a href={clean.startsWith("www.") ? `https://${clean}` : clean} target="_blank" rel="noreferrer">{clean}</a>{trailing}</span>;
  });
}
