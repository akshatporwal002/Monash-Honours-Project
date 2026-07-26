import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function FeedbackMarkdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        a: ({ children: linkText, href }) =>
          href ? (
            <a href={href} rel="noreferrer noopener">
              {linkText}
            </a>
          ) : (
            <span>{linkText}</span>
          ),
      }}
    >
      {children}
    </ReactMarkdown>
  )
}
