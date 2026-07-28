/**
 * Logo MapFeux.
 *
 * Une boussole dont un secteur est rompu, surmontant une flamme et un massif :
 * l'orientation, l'incertitude et le phénomène. Le secteur rouge marque la
 * portion de l'horizon que l'on n'observe pas — ce que le service dit de
 * lui-même avant toute donnée.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 300 340"
      className={className}
      role="img"
      aria-label="MapFeux"
      focusable="false"
    >
      <path fill="currentColor" d="M48 194 A108 108 0 0 0 252 194 L150 320 Z" />
      <circle cx="150" cy="138" r="91" fill="var(--surface)" />
      <g fill="none" strokeLinecap="butt" strokeWidth="17">
        <path stroke="currentColor" d="M60 94 A103 103 0 0 1 123 39" />
        <path stroke="currentColor" d="M134 35 A103 103 0 0 1 150 34" />
        <path stroke="var(--color-age-1)" d="M161 35 A103 103 0 0 1 231 71" />
        <path stroke="currentColor" d="M239 82 A103 103 0 0 1 253 128" />
        <path stroke="currentColor" d="M253 148 A103 103 0 0 1 238 196" />
        <path stroke="currentColor" d="M62 196 A103 103 0 0 1 47 148" />
        <path stroke="currentColor" d="M47 128 A103 103 0 0 1 55 105" />
      </g>
      <g fill="none" stroke="var(--color-carto)" strokeWidth="5">
        <path d="M89 119 A66 66 0 0 1 132 75" />
        <path d="M145 71 A66 66 0 0 1 207 108" />
        <path d="M211 122 A66 66 0 0 1 211 155" />
        <path d="M89 157 A66 66 0 0 1 89 124" />
        <path d="M79 138 H105" />
        <path d="M195 138 H221" />
        <path d="M150 67 V91" />
      </g>
      <path
        fill="var(--color-age-2)"
        d="M152 196 C119 174 113 151 126 127 C132 116 139 107 137 90 C158 103 169 121 164 140 C178 127 182 113 178 99 C202 116 208 139 197 160 C190 174 177 187 162 198 C176 176 170 160 158 151 C159 169 148 182 141 190 C139 179 134 168 124 160 C124 176 135 188 152 196 Z"
      />
      <path
        fill="currentColor"
        d="M70 226 L92 184 L108 212 L128 164 L149 213 L170 176 L190 215 L211 185 L233 226 Z"
      />
      <path fill="currentColor" d="M97 226 H203 L150 304 Z" />
    </svg>
  );
}
