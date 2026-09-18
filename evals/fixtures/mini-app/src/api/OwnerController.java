package com.example.mini;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;

// The prefix is on the class. A scan that reads the methods alone reports every path short
// and emits this annotation as a route of its own with the method "REQUEST".
@Controller
@RequestMapping("/owners/{ownerId}")
class OwnerController {

	@GetMapping("/exports/new")
	public String initCreationForm() {
		return "exports/createForm";
	}

	@PostMapping("/exports/new")
	public String processCreationForm() {
		return "redirect:/owners/{ownerId}";
	}

	// The brace form is ordinary Spring and was invisible to the scan.
	@GetMapping({ "/exports" })
	public String listExports() {
		return "exports/list";
	}
}
