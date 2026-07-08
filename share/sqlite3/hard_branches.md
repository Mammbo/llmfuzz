# sqlite3 — hard branches

9 hard branches (branch reached by the fuzzer, one side never taken). Ranked by how many times the taken side executed.

| # | location | function | unexplored | times reached |
|---|----------|----------|-----------|--------------|
| 1 | `sqlite3.c:134042` | `sqlite3.c:columnTypeImpl` | true arm never taken | 65517 |
| 2 | `sqlite3.c:101436` | `sqlite3.c:sqlite3ExprAffinity` | true arm never taken | 55710 |
| 3 | `sqlite3.c:106587` | `sqlite3.c:sqlite3ExprIfFalse` | true arm never taken | 21841 |
| 4 | `sqlite3.c:17630` | `sqlite3.c:sqlite3ExprCompareCollSeq` | true arm never taken | 13409 |
| 5 | `sqlite3.c:120257` | `sqlite3.c:patternCompare` | true arm never taken | 1223 |
| 6 | `sqlite3.c:120295` | `sqlite3.c:patternCompare` | false arm never taken | 774 |
| 7 | `sqlite3.c:156324` | `sqlite3.c:sqlite3WindowAlloc` | true arm never taken | 125 |
| 8 | `sqlite3.c:137412` | `sqlite3.c:resolveFromTermToCte` | true arm never taken | 60 |
| 9 | `sqlite3.c:148169` | `sqlite3.c:isAuxiliaryVtabOperator` | true arm never taken | 43 |

## 1. `sqlite3.c:134042`  (true arm never taken)
```c
134036            pS = pTabList->a[j].pSelect;
134037          }else{
134038            pNC = pNC->pNext;
134039          }
134040        }
134041  
134042        if( pTab==0 ){  <-- TARGET (unexplored)
134043          /* At one time, code such as "SELECT new.x" within a trigger would
134044          ** cause this condition to run.  Since then, we have restructured how
134045          ** trigger code is generated and so this condition is no longer
134046          ** possible. However, it can still be true for statements like
```

## 2. `sqlite3.c:101436`  (true arm never taken)
```c
101430      assert( pExpr->iColumn < pExpr->iTable );
101431      assert( pExpr->iTable==pExpr->pLeft->x.pSelect->pEList->nExpr );
101432      return sqlite3ExprAffinity(
101433          pExpr->pLeft->x.pSelect->pEList->a[pExpr->iColumn].pExpr
101434      );
101435    }
101436    if( op==TK_VECTOR ){  <-- TARGET (unexplored)
101437      return sqlite3ExprAffinity(pExpr->x.pList->a[0].pExpr);
101438    }
101439    return pExpr->affExpr;
101440  }
```

## 3. `sqlite3.c:106587`  (true arm never taken)
```c
106581      case TK_LT:
106582      case TK_LE:
106583      case TK_GT:
106584      case TK_GE:
106585      case TK_NE:
106586      case TK_EQ: {
106587        if( sqlite3ExprIsVector(pExpr->pLeft) ) goto default_expr;  <-- TARGET (unexplored)
106588        testcase( jumpIfNull==0 );
106589        r1 = sqlite3ExprCodeTemp(pParse, pExpr->pLeft, &regFree1);
106590        r2 = sqlite3ExprCodeTemp(pParse, pExpr->pRight, &regFree2);
106591        codeCompare(pParse, pExpr->pLeft, pExpr->pRight, op,
```

## 4. `sqlite3.c:17630`  (true arm never taken)
```c
17624  #define EP_Propagate (EP_Collate|EP_Subquery|EP_HasFunc)
17625  
17626  /*
17627  ** These macros can be used to test, set, or clear bits in the
17628  ** Expr.flags field.
17629  */
17630  #define ExprHasProperty(E,P)     (((E)->flags&(P))!=0)  <-- TARGET (unexplored)
17631  #define ExprHasAllProperty(E,P)  (((E)->flags&(P))==(P))
17632  #define ExprSetProperty(E,P)     (E)->flags|=(P)
17633  #define ExprClearProperty(E,P)   (E)->flags&=~(P)
17634  #define ExprAlwaysTrue(E)   (((E)->flags&(EP_FromJoin|EP_IsTrue))==EP_IsTrue)
```

## 5. `sqlite3.c:120257`  (true arm never taken)
```c
120251        }
120252        return SQLITE_NOWILDCARDMATCH;
120253      }
120254      if( c==matchOther ){
120255        if( pInfo->matchSet==0 ){
120256          c = sqlite3Utf8Read(&zPattern);
120257          if( c==0 ) return SQLITE_NOMATCH;  <-- TARGET (unexplored)
120258          zEscaped = zPattern;
120259        }else{
120260          u32 prior_c = 0;
120261          int seen = 0;
```

## 6. `sqlite3.c:120295`  (false arm never taken)
```c
120289          }
120290          continue;
120291        }
120292      }
120293      c2 = Utf8Read(zString);
120294      if( c==c2 ) continue;
120295      if( noCase  && sqlite3Tolower(c)==sqlite3Tolower(c2) && c<0x80 && c2<0x80 ){  <-- TARGET (unexplored)
120296        continue;
120297      }
120298      if( c==matchOne && zPattern!=zEscaped && c2!=0 ) continue;
120299      return SQLITE_NOMATCH;
```

## 7. `sqlite3.c:156324`  (true arm never taken)
```c
156318    **   UNBOUNDED FOLLOWING
156319    **
156320    ** The parser ensures that "UNBOUNDED PRECEDING" cannot be used as an ending
156321    ** boundary, and than "UNBOUNDED FOLLOWING" cannot be used as a starting
156322    ** frame boundary.
156323    */
156324    if( (eStart==TK_CURRENT && eEnd==TK_PRECEDING)  <-- TARGET (unexplored)
156325     || (eStart==TK_FOLLOWING && (eEnd==TK_PRECEDING || eEnd==TK_CURRENT))
156326    ){
156327      sqlite3ErrorMsg(pParse, "unsupported frame specification");
156328      goto windowAllocErr;
```

## 8. `sqlite3.c:137412`  (true arm never taken)
```c
137406    }
137407    if( pParse->nErr ){
137408      /* Prior errors might have left pParse->pWith in a goofy state, so
137409      ** go no further. */
137410      return 0;
137411    }
137412    if( pFrom->zDatabase!=0 ){  <-- TARGET (unexplored)
137413      /* The FROM term contains a schema qualifier (ex: main.t1) and so
137414      ** it cannot possibly be a CTE reference. */
137415      return 0;
137416    }
```

## 9. `sqlite3.c:148169`  (true arm never taken)
```c
148163      };
148164      ExprList *pList;
148165      Expr *pCol;                     /* Column reference */
148166      int i;
148167  
148168      pList = pExpr->x.pList;
148169      if( pList==0 || pList->nExpr!=2 ){  <-- TARGET (unexplored)
148170        return 0;
148171      }
148172  
148173      /* Built-in operators MATCH, GLOB, LIKE, and REGEXP attach to a
```
