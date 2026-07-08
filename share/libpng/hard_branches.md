# libpng — hard branches

10 hard branches (branch reached by the fuzzer, one side never taken). Ranked by how many times the taken side executed.

| # | location | function | unexplored | times reached |
|---|----------|----------|-----------|--------------|
| 1 | `pngrutil.c:135` | `png_read_sig` | true arm never taken | 1717 |
| 2 | `pngrutil.c:210` | `png_read_chunk_header` | true arm never taken | 2215 |
| 3 | `pngrutil.c:3288` | `png_handle_chunk` | true arm never taken | 2080 |
| 4 | `png.c:2030` | `png_check_IHDR` | true arm never taken | 168 |
| 5 | `png.c:2039` | `png_check_IHDR` | true arm never taken | 168 |
| 6 | `pngrutil.c:984` | `pngrutil.c:png_handle_PLTE` | true arm never taken | 115 |
| 7 | `pngrutil.c:1715` | `pngrutil.c:png_handle_tRNS` | true arm never taken | 13 |
| 8 | `pngrutil.c:1784` | `pngrutil.c:png_handle_bKGD` | true arm never taken | 11 |
| 9 | `pngrutil.c:1807` | `pngrutil.c:png_handle_bKGD` | true arm never taken | 10 |
| 10 | `png.c:1680` | `png_icc_check_header` | true arm never taken | 35 |

## 1. `pngrutil.c:135`  (true arm never taken)
```c
  129  #endif
  130  
  131     /* The signature must be serialized in a single I/O call. */
  132     png_read_data(png_ptr, &(info_ptr->signature[num_checked]), num_to_check);
  133     png_ptr->sig_bytes = 8;
  134  
  135     if (png_sig_cmp(info_ptr->signature, num_checked, num_to_check) != 0)  <-- TARGET (unexplored)
  136     {
  137        if (num_checked < 4 &&
  138            png_sig_cmp(info_ptr->signature, num_checked, num_to_check - 4) != 0)
  139           png_error(png_ptr, "Not a PNG file");
```

## 2. `pngrutil.c:210`  (true arm never taken)
```c
  204     png_debug2(0, "Reading chunk typeid = 0x%lx, length = %lu",
  205         (unsigned long)png_ptr->chunk_name, (unsigned long)length);
  206  
  207     /* Sanity check the length (first by <= 0x80) and the chunk name.  An error
  208      * here indicates a broken stream and libpng has no recovery from this.
  209      */
  210     if (buf[0] >= 0x80U)  <-- TARGET (unexplored)
  211        png_chunk_error(png_ptr, "bad header (invalid length)");
  212  
  213     /* Check to see if chunk name is valid. */
  214     if (!check_chunk_name(chunk_name))
```

## 3. `pngrutil.c:3288`  (true arm never taken)
```c
 3282     /* Is this a known chunk?  If not there are no checks performed here;
 3283      * png_handle_unknown does the correct checks.  This means that the values
 3284      * for known but unsupported chunks in the above table are not used here
 3285      * however the chunks_seen fields in png_struct are still set.
 3286      */
 3287     if (chunk_index == PNG_INDEX_unknown ||
 3288         read_chunks[chunk_index].handler == NULL)  <-- TARGET (unexplored)
 3289     {
 3290        handled = png_handle_unknown(
 3291              png_ptr, info_ptr, length, PNG_HANDLE_CHUNK_AS_DEFAULT);
 3292     }
```

## 4. `png.c:2030`  (true arm never taken)
```c
 2024         color_type == 5 || color_type > 6)
 2025     {
 2026        png_warning(png_ptr, "Invalid color type in IHDR");
 2027        error = 1;
 2028     }
 2029  
 2030     if (((color_type == PNG_COLOR_TYPE_PALETTE) && bit_depth > 8) ||  <-- TARGET (unexplored)
 2031         ((color_type == PNG_COLOR_TYPE_RGB ||
 2032           color_type == PNG_COLOR_TYPE_GRAY_ALPHA ||
 2033           color_type == PNG_COLOR_TYPE_RGB_ALPHA) && bit_depth < 8))
 2034     {
```

## 5. `png.c:2039`  (true arm never taken)
```c
 2033           color_type == PNG_COLOR_TYPE_RGB_ALPHA) && bit_depth < 8))
 2034     {
 2035        png_warning(png_ptr, "Invalid color type/bit depth combination in IHDR");
 2036        error = 1;
 2037     }
 2038  
 2039     if (interlace_type >= PNG_INTERLACE_LAST)  <-- TARGET (unexplored)
 2040     {
 2041        png_warning(png_ptr, "Unknown interlace method in IHDR");
 2042        error = 1;
 2043     }
```

## 6. `pngrutil.c:984`  (true arm never taken)
```c
  978     if ((png_ptr->mode & PNG_HAVE_PLTE) != 0)
  979        errmsg = "duplicate";
  980  
  981     else if ((png_ptr->mode & PNG_HAVE_IDAT) != 0)
  982        errmsg = "out of place";
  983  
  984     else if ((png_ptr->color_type & PNG_COLOR_MASK_COLOR) == 0)  <-- TARGET (unexplored)
  985        errmsg = "ignored in grayscale PNG";
  986  
  987     else if (length > 3*PNG_MAX_PALETTE_LENGTH || (length % 3) != 0)
  988        errmsg = "invalid";
```

## 7. `pngrutil.c:1715`  (true arm never taken)
```c
 1709        png_ptr->trans_color.green = png_get_uint_16(buf + 2);
 1710        png_ptr->trans_color.blue = png_get_uint_16(buf + 4);
 1711     }
 1712  
 1713     else if (png_ptr->color_type == PNG_COLOR_TYPE_PALETTE)
 1714     {
 1715        if ((png_ptr->mode & PNG_HAVE_PLTE) == 0)  <-- TARGET (unexplored)
 1716        {
 1717           png_crc_finish(png_ptr, length);
 1718           png_chunk_benign_error(png_ptr, "out of place");
 1719           return handled_error;
```

## 8. `pngrutil.c:1784`  (true arm never taken)
```c
 1778     else if ((png_ptr->color_type & PNG_COLOR_MASK_COLOR) != 0)
 1779        truelen = 6;
 1780  
 1781     else
 1782        truelen = 2;
 1783  
 1784     if (length != truelen)  <-- TARGET (unexplored)
 1785     {
 1786        png_crc_finish(png_ptr, length);
 1787        png_chunk_benign_error(png_ptr, "invalid");
 1788        return handled_error;
```

## 9. `pngrutil.c:1807`  (true arm never taken)
```c
 1801     if (png_ptr->color_type == PNG_COLOR_TYPE_PALETTE)
 1802     {
 1803        background.index = buf[0];
 1804  
 1805        if (info_ptr != NULL && info_ptr->num_palette != 0)
 1806        {
 1807           if (buf[0] >= info_ptr->num_palette)  <-- TARGET (unexplored)
 1808           {
 1809              png_chunk_benign_error(png_ptr, "invalid index");
 1810              return handled_error;
 1811           }
```

## 10. `png.c:1680`  (true arm never taken)
```c
 1674      * almost certainly more correct to ignore the profile.
 1675      */
 1676     temp = png_get_uint_32(profile+16); /* data colour space field */
 1677     switch (temp)
 1678     {
 1679        case 0x52474220: /* 'RGB ' */
 1680           if ((color_type & PNG_COLOR_MASK_COLOR) == 0)  <-- TARGET (unexplored)
 1681              return png_icc_profile_error(png_ptr, name, temp,
 1682                  "RGB color space not permitted on grayscale PNG");
 1683           break;
 1684  
```
