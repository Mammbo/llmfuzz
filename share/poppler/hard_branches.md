# poppler — hard branches

8 hard branches (branch reached by the fuzzer, one side never taken). Ranked by how many times the taken side executed.

| # | location | function | unexplored | times reached |
|---|----------|----------|-----------|--------------|
| 1 | `Stream.cc:264` | `_ZN6Stream10makeFilterEPKcPS_P6ObjectiP4Dict` | true arm never taken | 279515 |
| 2 | `XRef.cc:806` | `_ZN4XRef21readXRefStreamSectionEP6StreamPKiii` | true arm never taken | 1 |
| 3 | `XRef.cc:584` | `_ZN4XRef13readXRefTableEP6ParserPxPSt6vectorIxSaIxEEPS3_IiSaIiEE` | false arm never taken | 1 |
| 4 | `XRef.cc:619` | `_ZN4XRef13readXRefTableEP6ParserPxPSt6vectorIxSaIxEEPS3_IiSaIiEE` | true arm never taken | 1969 |
| 5 | `XRef.cc:743` | `_ZN4XRef14readXRefStreamEP6StreamPx` | true arm never taken | 1265 |
| 6 | `Parser.cc:294` | `_ZN6Parser10makeStreamEO6ObjectPKh14CryptAlgorithmiiiib` | true arm never taken | 2794 |
| 7 | `Catalog.cc:226` | `_ZN7Catalog13cachePageTreeEi` | false arm never taken | 12328 |
| 8 | `Catalog.cc:311` | `_ZN7Catalog13cachePageTreeEi` | true arm never taken | 12732 |

## 1. `Stream.cc:264`  (true arm never taken)
```c
  258      int early;
  259      int encoding;
  260      bool endOfLine, byteAlign, endOfBlock, black, damagedRowsBeforeError;
  261      int columns, rows;
  262      Object obj;
  263  
  264      if (!strcmp(name, "ASCIIHexDecode") || !strcmp(name, "AHx")) {  <-- TARGET (unexplored)
  265          str = new ASCIIHexStream(str);
  266      } else if (!strcmp(name, "ASCII85Decode") || !strcmp(name, "A85")) {
  267          str = new ASCII85Stream(str);
  268      } else if (!strcmp(name, "LZWDecode") || !strcmp(name, "LZW")) {
```

## 2. `XRef.cc:806`  (true arm never taken)
```c
  800              if ((c = xrefStr->getChar()) == EOF) {
  801                  return false;
  802              }
  803              gen = (gen << 8) + c;
  804          }
  805          if (gen > INT_MAX) {
  806              if (i == 0 && gen == std::numeric_limits<uint32_t>::max()) {  <-- TARGET (unexplored)
  807                  // workaround broken generators
  808                  gen = 65535;
  809              } else {
  810                  error(errSyntaxError, -1, "Gen inside xref table too large (bigger than INT_MAX)");
```

## 3. `XRef.cc:584`  (false arm never taken)
```c
  578                  entries[i].flags = entry.flags;
  579                  entries[i].obj.setToNull();
  580  
  581                  // PDF files of patents from the IBM Intellectual Property
  582                  // Network have a bug: the xref table claims to start at 1
  583                  // instead of 0.
  584                  if (i == 1 && first == 1 && entries[1].offset == 0 && entries[1].gen == 65535 && entries[1].type == xrefEntryFree) {  <-- TARGET (unexplored)
  585                      i = first = 0;
  586                      entries[0].offset = 0;
  587                      entries[0].gen = 65535;
  588                      entries[0].type = xrefEntryFree;
```

## 4. `XRef.cc:619`  (true arm never taken)
```c
  613              *pos = pos2;
  614              more = true;
  615          } else {
  616              error(errSyntaxWarning, -1, "Infinite loop in xref table");
  617              more = false;
  618          }
  619      } else if (obj2.isRef()) {  <-- TARGET (unexplored)
  620          // certain buggy PDF generators generate "/Prev NNN 0 R" instead
  621          // of "/Prev NNN"
  622          pos2 = (unsigned int)obj2.getRefNum();
  623          if (pos2 != *pos) {
```

## 5. `XRef.cc:743`  (true arm never taken)
```c
  737      }
  738  
  739      obj = dict->lookupNF("Prev").copy();
  740      if (obj.isInt() && obj.getInt() >= 0) {
  741          *pos = obj.getInt();
  742          more = true;
  743      } else if (obj.isInt64() && obj.getInt64() >= 0) {  <-- TARGET (unexplored)
  744          *pos = obj.getInt64();
  745          more = true;
  746      } else {
  747          more = false;
```

## 6. `Parser.cc:294`  (true arm never taken)
```c
  288          error(errSyntaxError, getPos(), "Missing 'endstream' or incorrect stream length");
  289          if (strict)
  290              return nullptr;
  291          if (lexer.hasXRef() && lexer.getStream()) {
  292              // shift until we find the proper endstream or we change to another object or reach eof
  293              length = lexer.getPos() - pos;
  294              if (buf1.isCmd("endstream")) {  <-- TARGET (unexplored)
  295                  dict.dictSet("Length", Object(length));
  296              }
  297          } else {
  298              // When building the xref we can't use it so use this
```

## 7. `Catalog.cc:226`  (false arm never taken)
```c
  220          Ref pagesRef;
  221  
  222          Object catDict = xref->getCatalog();
  223  
  224          if (catDict.isDict()) {
  225              const Object &pagesDictRef = catDict.dictLookupNF("Pages");
  226              if (pagesDictRef.isRef() && pagesDictRef.getRefNum() >= 0 && pagesDictRef.getRefNum() < xref->getNumObjects()) {  <-- TARGET (unexplored)
  227                  pagesRef = pagesDictRef.getRef();
  228              } else {
  229                  error(errSyntaxError, -1, "Catalog dictionary does not contain a valid \"Pages\" entry");
  230                  return false;
```

## 8. `Catalog.cc:311`  (true arm never taken)
```c
  305              auto p = std::make_unique<Page>(doc, pages.size() + 1, std::move(kid), kidRef.getRef(), attrs, form);
  306              if (!p->isOk()) {
  307                  error(errSyntaxError, -1, "Failed to create page (page {0:uld})", pages.size() + 1);
  308                  return false;
  309              }
  310  
  311              if (pages.size() >= std::size_t(numPages)) {  <-- TARGET (unexplored)
  312                  error(errSyntaxError, -1, "Page count in top-level pages object is incorrect");
  313                  return false;
  314              }
  315  
```
