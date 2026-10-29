"""
memory.py
Session memory: limits the shopper set earlier (budget, material, colour,
size) keep applying to later questions, together with the category being
discussed, so "show me cotton ones" after "a kurta under ₹2,000" means
cotton kurtas under ₹2,000.
"""
from dataclasses import asdict, dataclass

LIMITS = ["colour", "material", "size", "max_price"]


@dataclass
class SessionMemory:
    category: str = None
    sub_category: str = None
    colour: str = None
    material: str = None
    size: str = None
    max_price: int = None

    def apply(self, p):
        """Combine this turn's parsed query with memory. Returns the filters to use."""
        own = {k: getattr(p, k) for k in ["category", "sub_category"] + LIMITS}
        own["in_stock"] = p.in_stock

        # A question about one named product, or about something we do not
        # sell, is a new topic: answer it on its own and leave memory alone.
        if not p.category and (p.named_words or p.unknown_words):
            return own

        if p.category:
            if p.category != self.category:
                # new category: colour, material and size no longer make sense, budget stays
                self.colour = self.material = self.size = None
            self.category, self.sub_category = p.category, p.sub_category
        for key in LIMITS:
            if own[key] is not None:
                setattr(self, key, own[key])  # a new value replaces the old one
        return {**self.as_dict(), "in_stock": p.in_stock}

    def as_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}

    def reset(self):
        self.__init__()
