import { Component, Input, Output, EventEmitter } from '@angular/core';

@Component({
  selector: 'app-navbar',
  standalone: true,
  template: `
    <header class="navbar">
      <div class="logo">PideAlToke</div>
      <div class="user-info">
        <span>{{ userName }}</span>
        <button (click)="logout.emit()">Cerrar Sesión</button>
      </div>
    </header>
  `,
  styles: [`
    .navbar { display: flex; justify-content: space-between; padding: 1rem 2rem; background: #1e293b; color: white; align-items: center; }
    .user-info { display: flex; gap: 1rem; align-items: center; }
    button { background: #ef4444; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; }
  `]
})
export class NavbarComponent {
  @Input() userName: string = '';
  @Output() logout = new EventEmitter<void>();
}