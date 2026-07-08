# openssl — hard branches

8 hard branches (branch reached by the fuzzer, one side never taken). Ranked by how many times the taken side executed.

| # | location | function | unexplored | times reached |
|---|----------|----------|-----------|--------------|
| 1 | `asn1_lib.c:123` | `asn1_lib.c:asn1_get_length` | true arm never taken | 37335682 |
| 2 | `tasn_dec.c:1170` | `tasn_dec.c:asn1_check_tlen` | true arm never taken | 1488572 |
| 3 | `tasn_dec.c:89` | `ASN1_tag2bit` | true arm never taken | 80600 |
| 4 | `a_object.c:231` | `d2i_ASN1_OBJECT` | true arm never taken | 269435 |
| 5 | `a_object.c:257` | `ossl_c2i_ASN1_OBJECT` | true arm never taken | 518957 |
| 6 | `a_time.c:105` | `ossl_asn1_time_to_tm` | true arm never taken | 1727 |
| 7 | `a_time.c:129` | `ossl_asn1_time_to_tm` | false arm never taken | 11084 |
| 8 | `a_time.c:195` | `ossl_asn1_time_to_tm` | true arm never taken | 408 |

## 1. `asn1_lib.c:123`  (true arm never taken)
```c
  117                             long max)
  118  {
  119      const unsigned char *p = *pp;
  120      unsigned long ret = 0;
  121      int i;
  122  
  123      if (max-- < 1)  <-- TARGET (unexplored)
  124          return 0;
  125      if (*p == 0x80) {
  126          *inf = 1;
  127          p++;
```

## 2. `tasn_dec.c:1170`  (true arm never taken)
```c
 1164              ctx->hdrlen = p - q;
 1165              ctx->valid = 1;
 1166              /*
 1167               * If definite length, and no error, length + header can't exceed
 1168               * total amount of data available.
 1169               */
 1170              if ((i & 0x81) == 0 && (plen + ctx->hdrlen) > len) {  <-- TARGET (unexplored)
 1171                  ERR_raise(ERR_LIB_ASN1, ASN1_R_TOO_LONG);
 1172                  goto err;
 1173              }
 1174          }
```

## 3. `tasn_dec.c:89`  (true arm never taken)
```c
   83      /* tags 28-31 */
   84      B_ASN1_UNIVERSALSTRING, B_ASN1_UNKNOWN, B_ASN1_BMPSTRING, B_ASN1_UNKNOWN,
   85  };
   86  
   87  unsigned long ASN1_tag2bit(int tag)
   88  {
   89      if ((tag < 0) || (tag > 30))  <-- TARGET (unexplored)
   90          return 0;
   91      return tag2bit[tag];
   92  }
   93  
```

## 4. `a_object.c:231`  (true arm never taken)
```c
  225      inf = ASN1_get_object(&p, &len, &tag, &xclass, length);
  226      if (inf & 0x80) {
  227          i = ASN1_R_BAD_OBJECT_HEADER;
  228          goto err;
  229      }
  230  
  231      if (tag != V_ASN1_OBJECT) {  <-- TARGET (unexplored)
  232          i = ASN1_R_EXPECTING_AN_OBJECT;
  233          goto err;
  234      }
  235      ret = ossl_c2i_ASN1_OBJECT(a, &p, len);
```

## 5. `a_object.c:257`  (true arm never taken)
```c
  251  
  252      /*
  253       * Sanity check OID encoding. Need at least one content octet. MSB must
  254       * be clear in the last octet. can't have leading 0x80 in subidentifiers,
  255       * see: X.690 8.19.2
  256       */
  257      if (len <= 0 || len > INT_MAX || pp == NULL || (p = *pp) == NULL ||  <-- TARGET (unexplored)
  258          p[len - 1] & 0x80) {
  259          ERR_raise(ERR_LIB_ASN1, ASN1_R_INVALID_OBJECT_ENCODING);
  260          return NULL;
  261      }
```

## 6. `a_time.c:105`  (true arm never taken)
```c
   99              min_l = 13;
  100              strict = 1;
  101          }
  102      } else if (d->type == V_ASN1_GENERALIZEDTIME) {
  103          end = 7;
  104          btz = 6;
  105          if (d->flags & ASN1_STRING_FLAG_X509_TIME) {  <-- TARGET (unexplored)
  106              min_l = 15;
  107              strict = 1;
  108          } else {
  109              min_l = 13;
```

## 7. `a_time.c:129`  (false arm never taken)
```c
  123       * first two fields 00 to 99
  124       */
  125  
  126      if (l < min_l)
  127          goto err;
  128      for (i = 0; i < end; i++) {
  129          if (!strict && (i == btz) && ((a[o] == upper_z) || (a[o] == plus) || (a[o] == minus))) {  <-- TARGET (unexplored)
  130              i++;
  131              break;
  132          }
  133          if (!ossl_ascii_isdigit(a[o]))
```

## 8. `a_time.c:195`  (true arm never taken)
```c
  189  
  190      /*
  191       * Optional fractional seconds: decimal point followed by one or more
  192       * digits.
  193       */
  194      if (d->type == V_ASN1_GENERALIZEDTIME && a[o] == period) {
  195          if (strict)  <-- TARGET (unexplored)
  196              /* RFC 5280 forbids fractional seconds */
  197              goto err;
  198          if (++o == l)
  199              goto err;
```
