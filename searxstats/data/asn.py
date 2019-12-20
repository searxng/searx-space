from searxstats.model import AsnPrivacy

ASN_PRIVACY = {
    # CloudFlare
    "13335": AsnPrivacy.BAD,
    # Google, YouTube (for Google Fiber see AS16591 record)
    "15169": AsnPrivacy.BAD,
    # Amazon Web Services
    "16509": AsnPrivacy.BAD,
    # Alibaba
    # "45102": AsnPrivacy.BAD
}
