# libsndfile — hard branches

8 hard branches (branch reached by the fuzzer, one side never taken). Ranked by how many times the taken side executed.

| # | location | function | unexplored | times reached |
|---|----------|----------|-----------|--------------|
| 1 | `ima_adpcm.c:449` | `ima_adpcm.c:wavlike_ima_decode_block` | true arm never taken | 2925064 |
| 2 | `ms_adpcm.c:292` | `ms_adpcm.c:msadpcm_decode_block` | true arm never taken | 2076560 |
| 3 | `aiff.c:832` | `aiff.c:aiff_read_header` | false arm never taken | 8367 |
| 4 | `flac.c:172` | `flac.c:flac_buffer_copy` | true arm never taken | 311552 |
| 5 | `wav.c:362` | `wav.c:wav_read_header` | true arm never taken | 717 |
| 6 | `aiff.c:1055` | `aiff.c:aiff_read_comm_chunk` | true arm never taken | 746 |
| 7 | `nist.c:222` | `nist.c:nist_read_header` | true arm never taken | 8 |
| 8 | `caf.c:407` | `caf.c:caf_read_header` | true arm never taken | 2649 |

## 1. `ima_adpcm.c:449`  (true arm never taken)
```c
  443  		indxstart += 8 * pima->channels ;
  444  		} ;
  445  
  446  	/* Decode the encoded 4 bit samples. */
  447  
  448  	for (k = pima->channels ; k < (pima->samplesperblock * pima->channels) ; k ++)
  449  	{	chan = (pima->channels > 1) ? (k % 2) : 0 ;  <-- TARGET (unexplored)
  450  
  451  		bytecode = pima->samples [k] & 0xF ;
  452  
  453  		step = ima_step_size [stepindx [chan]] ;
```

## 2. `ms_adpcm.c:292`  (true arm never taken)
```c
  286  		pms->samples [sampleindx++] = bytecode & 0x0F ;
  287  		} ;
  288  
  289  	/* Decode the encoded 4 bit samples. */
  290  
  291  	for (k = 2 * pms->channels ; k < (pms->samplesperblock * pms->channels) ; k ++)
  292  	{	chan = (pms->channels > 1) ? (k % 2) : 0 ;  <-- TARGET (unexplored)
  293  
  294  		bytecode = pms->samples [k] & 0xF ;
  295  
  296  		/* Compute next Adaptive Scale Factor (ASF) */
```

## 3. `aiff.c:832`  (false arm never taken)
```c
  826  							psf->cues->cue_points [n].chunk_start = 0 ;
  827  							psf->cues->cue_points [n].block_start = 0 ;
  828  							psf->cues->cue_points [n].sample_offset = position ;
  829  
  830  							pstr_len = (ch & 1) ? ch : ch + 1 ;
  831  
  832  							if (pstr_len < sizeof (ubuf.scbuf) - 1)  <-- TARGET (unexplored)
  833  							{	bytesread += psf_binheader_readf (psf, "b", ubuf.scbuf, pstr_len) ;
  834  								ubuf.scbuf [pstr_len] = 0 ;
  835  								}
  836  							else
```

## 4. `flac.c:172`  (true arm never taken)
```c
  166  flac_buffer_copy (SF_PRIVATE *psf)
  167  {	FLAC_PRIVATE* pflac = (FLAC_PRIVATE*) psf->codec_data ;
  168  	const FLAC__Frame *frame = pflac->frame ;
  169  	const int32_t* const *buffer = pflac->wbuffer ;
  170  	unsigned i = 0, j, offset, channels, len ;
  171  
  172  	if (psf->sf.channels != (int) frame->header.channels)  <-- TARGET (unexplored)
  173  	{	psf_log_printf (psf, "Error: FLAC frame changed from %d to %d channels\n"
  174  									"Nothing to do but to error out.\n" ,
  175  									psf->sf.channels, frame->header.channels) ;
  176  		psf->error = SFE_FLAC_CHANNEL_COUNT_CHANGED ;
```

## 5. `wav.c:362`  (true arm never taken)
```c
  356  							psf_log_printf (psf, "RIFF : %u\n", RIFFsize) ;
  357  						else
  358  							psf_log_printf (psf, "RIFX : %u\n", RIFFsize) ;
  359  					} ;
  360  
  361  					psf_binheader_readf (psf, "m", &marker) ;
  362  					if (marker != WAVE_MARKER)  <-- TARGET (unexplored)
  363  						return SFE_WAV_NO_WAVE ;
  364  					parsestage |= HAVE_WAVE ;
  365  					psf_log_printf (psf, "WAVE\n") ;
  366  					chunk_size = 0 ;
```

## 6. `aiff.c:1055`  (true arm never taken)
```c
 1049  
 1050  	/* Found some broken 'fl32' files with comm.samplesize == 16. Fix it here. */
 1051  	if ((comm_fmt->encoding == fl32_MARKER || comm_fmt->encoding == FL32_MARKER) && comm_fmt->sampleSize != 32)
 1052  	{	psf_log_printf (psf, "  Sample Size : %d (should be 32)\n", comm_fmt->sampleSize) ;
 1053  		comm_fmt->sampleSize = 32 ;
 1054  		}
 1055  	else if ((comm_fmt->encoding == fl64_MARKER || comm_fmt->encoding == FL64_MARKER) && comm_fmt->sampleSize != 64)  <-- TARGET (unexplored)
 1056  	{	psf_log_printf (psf, "  Sample Size : %d (should be 64)\n", comm_fmt->sampleSize) ;
 1057  		comm_fmt->sampleSize = 64 ;
 1058  		}
 1059  	else
```

## 7. `nist.c:222`  (true arm never taken)
```c
  216  		psf->sf.format |= psf->endian ;
  217  		} ;
  218  
  219  	if ((cptr = strstr (psf_header, "sample_sig_bits -i ")))
  220  		sscanf (cptr, "sample_sig_bits -i %d", &bitwidth) ;
  221  
  222  	if (strstr (psf_header, "channels_interleaved -s5 FALSE"))  <-- TARGET (unexplored)
  223  	{	psf_log_printf (psf, "Non-interleaved data unsupported.\n", str) ;
  224  		return SFE_NIST_BAD_ENCODING ;
  225  		} ;
  226  
```

## 8. `caf.c:407`  (true arm never taken)
```c
  401  		if (chunk_size > psf->filelength)
  402  			break ;
  403  
  404  		psf_store_read_chunk_u32 (&psf->rchunks, marker, psf_ftell (psf), chunk_size) ;
  405  
  406  		switch (marker)
  407  		{	case peak_MARKER :  <-- TARGET (unexplored)
  408  				psf_log_printf (psf, "%M : %D\n", marker, chunk_size) ;
  409  				if (chunk_size != CAF_PEAK_CHUNK_SIZE (psf->sf.channels))
  410  				{	psf_binheader_readf (psf, "j", (size_t) chunk_size) ;
  411  					psf_log_printf (psf, "*** File PEAK chunk %D should be %d.\n", chunk_size, CAF_PEAK_CHUNK_SIZE (psf->sf.channels)) ;
```
